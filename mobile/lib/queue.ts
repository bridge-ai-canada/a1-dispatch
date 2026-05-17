/* AsyncStorage-backed offline queue for retrying API calls after network restoration.
 * Flushes on a 20s timer + on demand (e.g. after a successful auth call). */
import AsyncStorage from "@react-native-async-storage/async-storage";
import { api } from "./api";

const QUEUE_KEY = "a1.queue.v1";
let flushing = false;

type QueueItem = {
    id: string;
    method: "post" | "patch" | "put" | "delete";
    url: string;
    data?: any;
    ts: number;
};

async function read(): Promise<QueueItem[]> {
    try { return JSON.parse((await AsyncStorage.getItem(QUEUE_KEY)) || "[]"); }
    catch { return []; }
}
async function write(q: QueueItem[]) {
    await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(q));
}

export async function enqueue(item: Omit<QueueItem, "id" | "ts">) {
    const q = await read();
    q.push({ ...item, id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, ts: Date.now() });
    await write(q);
}

export async function flush() {
    if (flushing) return { sent: 0, remaining: 0 };
    flushing = true;
    try {
        const q = await read();
        const remaining: QueueItem[] = [];
        let sent = 0;
        for (const it of q) {
            try {
                await (api as any)[it.method](it.url, it.data);
                sent++;
            } catch (_) {
                remaining.push(it);
            }
        }
        await write(remaining);
        return { sent, remaining: remaining.length };
    } finally {
        flushing = false;
    }
}

export async function queueSize(): Promise<number> {
    return (await read()).length;
}

let timer: any = null;
export function startAutoFlush() {
    if (timer) return;
    timer = setInterval(() => { flush(); }, 20_000);
}
