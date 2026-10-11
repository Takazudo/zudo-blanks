// Integrate this handler ONLY with the separately authorized old-host route.
// A redirect without a fragment lets browsers carry their original fragment forward.
export function redirectOldDocs(request) {
  const url = new URL(request.url);
  if (url.hostname !== 'takazudomodular.com' || !(url.pathname === '/pj/zblanks' || url.pathname.startsWith('/pj/zblanks/'))) return null;
  url.hostname = 'zudo-blanks.zudolab.dev';
  url.protocol = 'https:';
  url.port = '';
  // Keep the old path for the new host's explicit migration map (including viewers).
  return Response.redirect(url.href, 301);
}
