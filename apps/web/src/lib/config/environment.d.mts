export function validateEnvironment(env: Record<string, string | undefined>): {
  appEnvironment: string; authMode: string;
};
