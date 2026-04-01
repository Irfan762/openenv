import { Router, type IRouter, type Request, type Response, type NextFunction } from "express";
import { createProxyMiddleware } from "http-proxy-middleware";

const router: IRouter = Router();

const proxy = createProxyMiddleware({
  target: "http://localhost:8000",
  changeOrigin: true,
  pathRewrite: { "^/api/openenv": "" },
  on: {
    error: (_err: unknown, _req: Request, res: Response) => {
      (res as Response).status(502).json({
        error: "OpenEnv server is not running",
        hint: "Start it with: cd artifacts/openenv-datacleaning && uvicorn openenv_datacleaning.server:app --port 8000",
      });
    },
  },
});

router.use("/openenv", proxy as unknown as (req: Request, res: Response, next: NextFunction) => void);

export default router;
