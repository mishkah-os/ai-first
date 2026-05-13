
// Mostamal Hawaa Search Screen - MAS V2 ready module
export const searchScreenMeta = {
  project: 'mostamal-hawaa',
  route: '/search',
  title: 'Product search',
  intent: 'Help buyers filter used women-focused listings by keyword, category, city, condition, and price.'
};

export const searchFilters = {
  categories: ['Fashion', 'Beauty', 'Kids', 'Home', 'Electronics', 'Sports'],
  conditions: ['New', 'Like new', 'Used', 'Needs repair'],
  cities: ['Riyadh', 'Jeddah', 'Dammam', 'Makkah', 'Madinah']
};

export function filterListings(listings, query = {}) {
  const term = String(query.term || '').trim().toLowerCase();
  return (listings || []).filter((item) => {
    const haystack = [item.title, item.description, item.category, item.city, item.condition].join(' ').toLowerCase();
    if (term && !haystack.includes(term)) return false;
    if (query.category && item.category !== query.category) return false;
    if (query.city && item.city !== query.city) return false;
    if (query.condition && item.condition !== query.condition) return false;
    if (query.minPrice && Number(item.price || 0) < Number(query.minPrice)) return false;
    if (query.maxPrice && Number(item.price || 0) > Number(query.maxPrice)) return false;
    return true;
  });
}

export function MostamalSearchScreen(props = {}, D = window.MAS && window.MAS.D) {
  const db = props.db || {};
  const filters = db.filters || {};
  const listings = filterListings(db.listings || props.listings || [], filters);
  if (!D) return { listings, filters, meta: searchScreenMeta };
  return D.section({ class: 'mh-search-screen', dir: 'rtl' }, [
    D.header({ class: 'mh-search-head' }, [
      D.h1('البحث في مستعمل حواء'),
      D.p('فلترة حقيقية للإعلانات حسب القسم والمدينة والحالة والسعر.')
    ]),
    D.div({ class: 'mh-filter-grid' }, [
      D.input({ gkey: 'search.term', name: 'term', value: filters.term || '', placeholder: 'ابحثي عن منتج...' }),
      D.select({ gkey: 'search.category', name: 'category', value: filters.category || '' }, [D.option({ value: '' }, 'كل الأقسام')].concat(searchFilters.categories.map((x) => D.option({ value: x }, x)))),
      D.select({ gkey: 'search.city', name: 'city', value: filters.city || '' }, [D.option({ value: '' }, 'كل المدن')].concat(searchFilters.cities.map((x) => D.option({ value: x }, x)))),
      D.select({ gkey: 'search.condition', name: 'condition', value: filters.condition || '' }, [D.option({ value: '' }, 'كل الحالات')].concat(searchFilters.conditions.map((x) => D.option({ value: x }, x))))
    ]),
    D.div({ class: 'mh-results-count' }, `${listings.length} إعلان مطابق`),
    D.div({ class: 'mh-result-grid' }, listings.map((item) => D.article({ class: 'mh-result-card', key: item.id }, [
      D.strong(item.title || 'Listing'),
      D.span(`${item.price || 0} ر.س`),
      D.small(`${item.category || '-'} | ${item.city || '-'}`)
    ])))
  ]);
}

if (window.MAS && window.MAS.component) {
  window.MAS.component('mostamal-search-screen', (props, D) => MostamalSearchScreen(props, D));
}
