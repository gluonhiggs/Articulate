import * as net from "net";

/**
 * Find a free TCP port, starting from `startPort`.
 * Tries up to 20 consecutive ports before giving up.
 */
export function findFreePort(startPort: number = 8000): Promise<number> {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const maxAttempts = 20;

    const tryPort = (port: number) => {
      const server = net.createServer();
      server.unref();
      server.on("error", () => {
        attempts++;
        if (attempts >= maxAttempts) {
          reject(new Error(`No free port found in range ${startPort}–${startPort + maxAttempts - 1}`));
        } else {
          tryPort(port + 1);
        }
      });
      server.listen(port, "127.0.0.1", () => {
        const addr = server.address() as net.AddressInfo;
        server.close(() => resolve(addr.port));
      });
    };

    tryPort(startPort);
  });
}
