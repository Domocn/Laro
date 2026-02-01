export class DebugLogger {
  namespace: string;
  constructor(namespace: string) {
    this.namespace = namespace;
  }
  info(...args: any[]) { console.log(`[${this.namespace}]`, ...args); }
  warn(...args: any[]) { console.warn(`[${this.namespace}]`, ...args); }
  error(...args: any[]) { console.error(`[${this.namespace}]`, ...args); }
}

export const logStateChange = (namespace: string, state: string, data: any) => {
  console.log(`[${namespace}] State Change: ${state}`, data);
};

export const debug = {
  api: new DebugLogger('api'),
  auth: new DebugLogger('auth'),
  ui: new DebugLogger('ui'),
};

export const createApiDebugInterceptor = (instance: any) => {
  instance.interceptors.request.use((config: any) => {
    debug.api.info(`${config.method?.toUpperCase()} ${config.url}`, config.data);
    return config;
  });
  instance.interceptors.response.use(
    (response: any) => {
      debug.api.info(`Response from ${response.config.url}`, response.data);
      return response;
    },
    (error: any) => {
      debug.api.error(`Error from ${error.config?.url}`, error.response?.data || error.message);
      return Promise.reject(error);
    }
  );
};
