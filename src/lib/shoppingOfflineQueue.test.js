
/**
 * @jest-environment jsdom
 */
import {
  enqueueShoppingOp,
  flushShoppingOpsQueue,
  clearShoppingOpsQueue,
  peekShoppingOpsQueue,
} from './shoppingOfflineQueue';

describe('shoppingOfflineQueue', () => {
  beforeEach(() => {
    localStorage.clear();
    clearShoppingOpsQueue();
  });

  it('queues and flushes check/add/remove/aisle ops', async () => {
    enqueueShoppingOp({ type: 'check', listId: 'L1', itemIndex: 0, checked: true });
    enqueueShoppingOp({ type: 'add', listId: 'L1', item: { name: 'Milk' } });
    enqueueShoppingOp({ type: 'aisle', listId: 'L1', itemIndex: 1, aisle: 'Dairy' });
    enqueueShoppingOp({ type: 'remove', listId: 'L1', itemIndex: 2, itemName: 'Eggs' });
    expect(peekShoppingOpsQueue()).toHaveLength(4);

    const calls = [];
    const result = await flushShoppingOpsQueue({
      checkItem: async (...args) => { calls.push(['check', ...args]); },
      addItem: async (...args) => { calls.push(['add', ...args]); },
      removeItem: async (...args) => { calls.push(['remove', ...args]); },
      setItemAisle: async (...args) => { calls.push(['aisle', ...args]); },
    });
    expect(result.flushed).toBe(4);
    expect(result.remaining).toBe(0);
    expect(calls.map((c) => c[0])).toEqual(['check', 'add', 'aisle', 'remove']);
  });

  it('queues create_list and delete_list and cancels matching create', async () => {
    enqueueShoppingOp({ type: 'create_list', listId: 'tmp-1', name: 'Party' });
    enqueueShoppingOp({ type: 'delete_list', listId: 'tmp-1' });
    expect(peekShoppingOpsQueue()).toHaveLength(0);

    enqueueShoppingOp({ type: 'create_list', listId: 'tmp-2', name: 'BBQ' });
    enqueueShoppingOp({ type: 'delete_list', listId: 'L-real' });
    const calls = [];
    const result = await flushShoppingOpsQueue({
      checkItem: async () => {},
      addItem: async () => {},
      removeItem: async () => {},
      setItemAisle: async () => {},
      createList: async (entry) => { calls.push(['create', entry.name]); },
      deleteList: async (id) => { calls.push(['delete', id]); },
    });
    expect(result.flushed).toBe(2);
    expect(calls).toEqual([['create', 'BBQ'], ['delete', 'L-real']]);
  });

  it('coalesces repeated checks for the same item', () => {
    enqueueShoppingOp({ type: 'check', listId: 'L1', itemIndex: 3, checked: false });
    enqueueShoppingOp({ type: 'check', listId: 'L1', itemIndex: 3, checked: true });
    const q = peekShoppingOpsQueue().filter((e) => e.type === 'check');
    expect(q).toHaveLength(1);
    expect(q[0].checked).toBe(true);
  });
});
