import os from "node:os";

/**
 * Configuracion de Next.js.
 *
 * Dos cosas, las dos para poder usar la app desde el celular:
 *
 * 1. rewrites: todo lo que el navegador pide a /api/... Next lo reenvia a la
 *    API de FastAPI. El celular nunca habla directo con la API: habla con Next,
 *    y Next (que corre en tu PC) le pasa el pedido. Por eso no hace falta tocar
 *    CORS ni saber la IP de nadie.
 *
 * 2. allowedDevOrigins: en modo desarrollo (`npm run dev`), Next solo atiende
 *    del todo a los dispositivos que le nombramos. Esta lista son las IPs de
 *    ESTA computadora en tu red (ej. 192.168.0.23): se calculan solas, asi no
 *    hay que editar nada si el router te cambia la IP.
 */
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const lanIPs = Object.values(os.networkInterfaces())
  .flat()
  .filter((n) => n && n.family === "IPv4" && !n.internal)
  .map((n) => n.address);

const nextConfig = {
  allowedDevOrigins: lanIPs,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
