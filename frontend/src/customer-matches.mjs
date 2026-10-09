export function directoryMatches(items) {
  const matches=Object.create(null);
  for(const customer of items.filter(c=>c.active!==false)) {
    for(const name of [...(customer.aliases||[]),...(customer.external_id?[customer.external_id]:[])]) {
      if(matches[name]&&matches[name]!==customer.customer)throw new Error('A name or ID matches more than one customer. Fix Customers first.');
      matches[name]=customer.customer;
    }
  }
  return {...matches};
}
