import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'usr_id_token';
const SESSION_KEY = 'usr_session_data';

export const saveIdToken = async (token: string): Promise<void> => {
  await SecureStore.setItemAsync(TOKEN_KEY, token);
};

export const getIdToken = async (): Promise<string | null> => {
  return await SecureStore.getItemAsync(TOKEN_KEY);
};

export const clearIdToken = async (): Promise<void> => {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
};

export const saveSessionData = async (data: string): Promise<void> => {
  await SecureStore.setItemAsync(SESSION_KEY, data);
};

export const getSessionData = async (): Promise<string | null> => {
  return await SecureStore.getItemAsync(SESSION_KEY);
};

export const clearSessionData = async (): Promise<void> => {
  await SecureStore.deleteItemAsync(SESSION_KEY);
};
