import axios from "axios";
import Constants from "expo-constants";
import { getToken } from "./auth";

const fallback = (Constants.expoConfig?.extra as any)?.apiUrl
    || "https://a1-dispatch.preview.emergentagent.com";
export const API_URL = (process.env.API_URL || fallback).replace(/\/$/, "");

export const api = axios.create({
    baseURL: `${API_URL}/api`,
    timeout: 15000,
});

api.interceptors.request.use(async (config) => {
    const token = await getToken();
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
});
