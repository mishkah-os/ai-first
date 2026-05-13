
// Mostamal Hawaa Pricing Offer - operational pricing module
export const pricingPlans = [
  { id: 'starter', name: 'Starter Seller', monthly: 0, featuredAds: 0, commission: 0.03, audience: 'individual sellers' },
  { id: 'pro', name: 'Pro Boutique', monthly: 49, featuredAds: 12, commission: 0.018, audience: 'active home businesses' },
  { id: 'merchant', name: 'Merchant', monthly: 149, featuredAds: 40, commission: 0.01, audience: 'stores and high-volume sellers' }
];

export function calculateOffer(planId, options = {}) {
  const plan = pricingPlans.find((item) => item.id === planId) || pricingPlans[0];
  const months = Math.max(1, Number(options.months || 1));
  const adBoosts = Math.max(0, Number(options.adBoosts || 0));
  const subtotal = plan.monthly * months + adBoosts * 9;
  const discount = months >= 12 ? subtotal * 0.15 : months >= 6 ? subtotal * 0.08 : 0;
  return {
    plan,
    months,
    adBoosts,
    subtotal,
    discount,
    total: Math.max(0, subtotal - discount),
    currency: 'SAR'
  };
}

export function PricingOfferView(props = {}, D = window.MAS && window.MAS.D) {
  const selected = props.selected || 'pro';
  const offer = calculateOffer(selected, props.options || {});
  if (!D) return offer;
  return D.section({ class: 'mh-pricing-offer', dir: 'rtl' }, [
    D.header([D.h1('خطط مستعمل حواء للبائعين'), D.p('تسعير واضح للإعلانات المميزة والمتاجر المنزلية.')]),
    D.div({ class: 'mh-plan-grid' }, pricingPlans.map((plan) => D.article({ class: 'mh-plan' + (plan.id === selected ? ' active' : ''), key: plan.id }, [
      D.h2(plan.name),
      D.strong(`${plan.monthly} ر.س / شهر`),
      D.p(`${plan.featuredAds} إعلان مميز | عمولة ${(plan.commission * 100).toFixed(1)}%`),
      D.small(plan.audience)
    ]))),
    D.footer({ class: 'mh-offer-total' }, [`الإجمالي: ${offer.total.toFixed(2)} ${offer.currency}`])
  ]);
}

if (window.MAS && window.MAS.component) {
  window.MAS.component('mostamal-pricing-offer', (props, D) => PricingOfferView(props, D));
}
