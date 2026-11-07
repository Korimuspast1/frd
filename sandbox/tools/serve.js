#!/usr/bin/env node
/* Мини-сервер для локального запуска песочницы в браузере.
   Использование: node tools/serve.js [port]                       */
const http = require('http');
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..', 'app', 'src', 'main', 'assets');
const port = +(process.argv[2] || 8080);

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.woff2': 'font/woff2',
  '.png': 'image/png',
  '.json': 'application/json'
};

http.createServer((req, res) => {
  let url = decodeURIComponent(req.url.split('?')[0]);
  if (url === '/' || url === '') url = '/index.html';
  const file = path.join(root, path.normalize(url).replace(/^(\.\.[/\\])+/, ''));
  if (!file.startsWith(root)) { res.writeHead(403); return res.end('403'); }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); return res.end('404'); }
    res.writeHead(200, {
      'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream',
      'Cache-Control': 'no-store'
    });
    res.end(data);
  });
}).listen(port, '0.0.0.0', () => {
  console.log('Песочница: http://0.0.0.0:' + port);
});
