/// <reference types="vite/client" />

import axios from 'axios';

//API HTTP Router Handler 클라이언트
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});