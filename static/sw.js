// Carroo PWA service worker（インストール可能要件の充足が主目的）
self.addEventListener('install', (e) => self.skipWaiting());
self.addEventListener('activate', (e) => self.clients.claim());
self.addEventListener('fetch', (e) => {
  // ネットワーク優先（投稿系アプリのためオフラインキャッシュは行わない）
  return;
});
