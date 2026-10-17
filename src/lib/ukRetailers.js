/** UK online grocers — keep in sync with backend/utils/retailer_links.py */

export const UK_RETAILER_LABELS = {
  tesco: 'Tesco',
  sainsburys: "Sainsbury's",
  asda: 'Asda',
  morrisons: 'Morrisons',
  waitrose: 'Waitrose',
  ocado: 'Ocado',
  aldi: 'Aldi',
  lidl: 'Lidl',
  iceland: 'Iceland',
  marksandspencer: 'M&S Food',
  coop: 'Co-op',
  booths: 'Booths',
  amazon: 'Amazon',
};

export const UK_RETAILER_ORDER = Object.keys(UK_RETAILER_LABELS);

export function orderedRetailerEntries(links = {}) {
  const entries = Object.entries(links || {});
  entries.sort(([a], [b]) => {
    const ia = UK_RETAILER_ORDER.indexOf(a);
    const ib = UK_RETAILER_ORDER.indexOf(b);
    const oa = ia === -1 ? 999 : ia;
    const ob = ib === -1 ? 999 : ib;
    if (oa !== ob) return oa - ob;
    return a.localeCompare(b);
  });
  return entries;
}

export function retailerLabel(id) {
  return UK_RETAILER_LABELS[id] || id;
}
