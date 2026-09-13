/* Concursos Europa - service worker
   La app funciona sin conexión con los últimos datos descargados.
   Sube el número de CACHE al publicar cambios. */
const CACHE = "concursos-v3";
const CLAVE_DATOS = "datos-concursos";
const SHELL = [
  "./", "./index.html", "./manifest.webmanifest",
  "./icon-180.png", "./icon-192.png", "./icon-512.png",
  "./icon-maskable-512.png", "./favicon-64.png", "./concursos.json"
];

self.addEventListener("install", function(e){
  e.waitUntil(
    caches.open(CACHE)
      .then(function(c){ return c.addAll(SHELL); })
      .then(function(){ return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function(e){
  e.waitUntil(
    caches.keys()
      .then(function(ks){
        return Promise.all(ks.filter(function(k){ return k !== CACHE; })
                             .map(function(k){ return caches.delete(k); }));
      })
      .then(function(){ return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function(e){
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  const esDatos = url.pathname.endsWith("concursos.json");
  const esNavegacion = req.mode === "navigate";

  /* datos y documento: primero la red, y si no hay, lo guardado */
  if (esDatos || esNavegacion) {
    const clave = esDatos ? CLAVE_DATOS : req;
    e.respondWith(
      fetch(req).then(function(r){
        const copia = r.clone();
        caches.open(CACHE).then(function(c){ c.put(clave, copia); });
        return r;
      }).catch(function(){
        return caches.match(clave).then(function(r){
          return r || caches.match("./index.html");
        });
      })
    );
    return;
  }

  /* resto (iconos): primero lo guardado */
  e.respondWith(
    caches.match(req).then(function(r){
      return r || fetch(req).then(function(resp){
        const copia = resp.clone();
        caches.open(CACHE).then(function(c){ c.put(req, copia); });
        return resp;
      });
    })
  );
});
