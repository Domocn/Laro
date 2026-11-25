/**
 * KitchenOwl-style offline shopping mutation queue.
 * Queues check/uncheck, add, remove, and aisle moves while offline; flushes when back online.
 */
const STORAGE_KEY = 'laro_shopping_ops_queue_v2';
const LEGACY_CHECK_KEY = 'laro_shopping_check_queue_v1';

function readQueue() {
  try {
    migrateLegacyChecks();
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeQueue(queue) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
  } catch {
    /* ignore quota */
  }
}

function migrateLegacyChecks() {
  try {
    const raw = localStorage.getItem(LEGACY_CHECK_KEY);
    if (!raw) return;
    const legacy = JSON.parse(raw);
    if (!Array.isArray(legacy) || !legacy.length) {
      localStorage.removeItem(LEGACY_CHECK_KEY);
      return;
    }
    const existing = (() => {
      try {
        const r = localStorage.getItem(STORAGE_KEY);
        const p = r ? JSON.parse(r) : [];
        return Array.isArray(p) ? p : [];
      } catch {
        return [];
      }
    })();
    for (const e of legacy) {
      existing.push({
        type: 'check',
        listId: e.listId,
        itemIndex: e.itemIndex,
        checked: !!e.checked,
        ts: e.ts || Date.now(),
      });
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(existing));
    localStorage.removeItem(LEGACY_CHECK_KEY);
  } catch {
    /* ignore */
  }
}

/** @deprecated use enqueueShoppingOp({ type: 'check', ... }) */
export function enqueueShoppingCheck({ listId, itemIndex, checked }) {
  return enqueueShoppingOp({
    type: 'check',
    listId,
    itemIndex,
    checked: !!checked,
  });
}

export function enqueueShoppingOp(op) {
  if (!op?.type || !op?.listId) return readQueue().length;
  const queue = readQueue();

  if (op.type === 'check') {
    const filtered = queue.filter(
      (e) => !(e.type === 'check' && e.listId === op.listId && e.itemIndex === op.itemIndex)
    );
    filtered.push({
      type: 'check',
      listId: op.listId,
      itemIndex: op.itemIndex,
      checked: !!op.checked,
      ts: Date.now(),
    });
    writeQueue(filtered);
    return filtered.length;
  }

  if (op.type === 'aisle') {
    const filtered = queue.filter(
      (e) => !(e.type === 'aisle' && e.listId === op.listId && e.itemIndex === op.itemIndex)
    );
    filtered.push({
      type: 'aisle',
      listId: op.listId,
      itemIndex: op.itemIndex,
      aisle: op.aisle,
      remember: op.remember !== false,
      ts: Date.now(),
    });
    writeQueue(filtered);
    return filtered.length;
  }

  if (op.type === 'add') {
    queue.push({
      type: 'add',
      listId: op.listId,
      item: op.item,
      ts: Date.now(),
    });
    writeQueue(queue);
    return queue.length;
  }

  if (op.type === 'remove') {
    // Prefer removing a matching pending add for the same name when possible
    const name = (op.itemName || '').trim().toLowerCase();
    let filtered = queue;
    if (name) {
      const addIdx = [...queue]
        .map((e, i) => ({ e, i }))
        .reverse()
        .find(
          ({ e }) =>
            e.type === 'add' &&
            e.listId === op.listId &&
            String(e.item?.name || '')
              .trim()
              .toLowerCase() === name
        )?.i;
      if (addIdx != null) {
        filtered = queue.filter((_, i) => i !== addIdx);
        writeQueue(filtered);
        return filtered.length;
      }
    }
    filtered = queue.filter(
      (e) => !(e.type === 'remove' && e.listId === op.listId && e.itemIndex === op.itemIndex)
    );
    filtered.push({
      type: 'remove',
      listId: op.listId,
      itemIndex: op.itemIndex,
      itemName: op.itemName,
      ts: Date.now(),
    });
    writeQueue(filtered);
    return filtered.length;
  }


  if (op.type === 'create_list') {
    queue.push({
      type: 'create_list',
      listId: op.listId, // client temp id for correlation
      name: op.name,
      items: op.items || [],
      ts: Date.now(),
    });
    writeQueue(queue);
    return queue.length;
  }

  if (op.type === 'delete_list') {
    // Cancel a pending offline create for the same id — nothing to sync.
    const hadPendingCreate = queue.some(
      (e) => e.type === 'create_list' && e.listId === op.listId
    );
    let filtered = queue.filter(
      (e) => !(e.type === 'create_list' && e.listId === op.listId)
    );
    filtered = filtered.filter(
      (e) => !(e.type === 'delete_list' && e.listId === op.listId)
    );
    // Drop item ops targeting this list
    filtered = filtered.filter((e) => e.listId !== op.listId);
    if (!hadPendingCreate && !String(op.listId || '').startsWith('tmp-')) {
      filtered.push({
        type: 'delete_list',
        listId: op.listId,
        ts: Date.now(),
      });
    }
    writeQueue(filtered);
    return filtered.length;
  }

  queue.push({ ...op, ts: Date.now() });
  writeQueue(queue);
  return queue.length;
}

export function peekShoppingCheckQueue() {
  return readQueue();
}

export function peekShoppingOpsQueue() {
  return readQueue();
}

/**
 * @param {object} handlers
 * @param {(listId: string, itemIndex: number, checked: boolean) => Promise<any>} handlers.checkItem
 * @param {(listId: string, item: object) => Promise<any>} handlers.addItem
 * @param {(listId: string, itemIndex: number) => Promise<any>} handlers.removeItem
 * @param {(listId: string, itemIndex: number, aisle: string, remember?: boolean) => Promise<any>} handlers.setItemAisle
 */
export async function flushShoppingOpsQueue(handlers = {}) {
  const queue = readQueue();
  if (!queue.length) return { flushed: 0, remaining: 0 };

  const {
    checkItem,
    addItem,
    removeItem,
    setItemAisle,
    createList,
    deleteList,
  } = handlers;

  // Keep index-based ops stable: process per-list in order
  const remaining = [];
  let flushed = 0;

  for (const entry of queue) {
    try {
      if (entry.type === 'check') {
        if (!checkItem) throw new Error('checkItem handler missing');
        await checkItem(entry.listId, entry.itemIndex, entry.checked);
      } else if (entry.type === 'add') {
        if (!addItem) throw new Error('addItem handler missing');
        await addItem(entry.listId, entry.item);
      } else if (entry.type === 'remove') {
        if (!removeItem) throw new Error('removeItem handler missing');
        await removeItem(entry.listId, entry.itemIndex);
      } else if (entry.type === 'aisle') {
        if (!setItemAisle) throw new Error('setItemAisle handler missing');
        await setItemAisle(entry.listId, entry.itemIndex, entry.aisle, entry.remember !== false);
      } else if (entry.type === 'create_list') {
        if (!createList) throw new Error('createList handler missing');
        await createList(entry);
      } else if (entry.type === 'delete_list') {
        if (!deleteList) throw new Error('deleteList handler missing');
        await deleteList(entry.listId);
      } else {
        remaining.push(entry);
        continue;
      }
      flushed += 1;
    } catch {
      remaining.push(entry);
    }
  }

  writeQueue(remaining);
  return { flushed, remaining: remaining.length };
}

/** @deprecated use flushShoppingOpsQueue */
export async function flushShoppingCheckQueue(checkItemFn) {
  return flushShoppingOpsQueue({ checkItem: checkItemFn });
}

export function clearShoppingCheckQueue() {
  writeQueue([]);
}

export function clearShoppingOpsQueue() {
  writeQueue([]);
}
