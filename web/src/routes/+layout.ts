// The whole studio prerenders: there is no server. Every route below this
// layout must be expressible as static HTML at build time — adapter-static
// runs in strict mode, so a route that cannot prerender fails the build
// loudly instead of quietly gaining a runtime dependency.
export const prerender = true;
