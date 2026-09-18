import { writable } from 'svelte/store';

// 研磨机页 → 工艺卡页 跳转时预选机台
export const processCardMillId = writable<number | null>(null);
