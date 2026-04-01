import { Router, type IRouter } from "express";
import healthRouter from "./health";
import openenvProxyRouter from "./openenv-proxy";

const router: IRouter = Router();

router.use(healthRouter);
router.use(openenvProxyRouter);

export default router;
