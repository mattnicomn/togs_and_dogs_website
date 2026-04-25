const CONFIG = {
  API_URL: import.meta.env.VITE_API_URL || "https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod",
  REGION: import.meta.env.VITE_REGION || "us-east-1",
  USER_POOL_ID: import.meta.env.VITE_COGNITO_USER_POOL_ID || "us-east-1_counlsXGU",
  CLIENT_ID: import.meta.env.VITE_COGNITO_CLIENT_ID || "1u4t7rfo339nkcgaf6q8s8sc6u"
};

export default CONFIG;
