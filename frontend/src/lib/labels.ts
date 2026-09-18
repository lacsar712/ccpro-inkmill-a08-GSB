import type { MillStatus, ProcessCardStatus } from './types';

export const millStatusLabel: Record<MillStatus, string> = {
  grinding: '研磨中',
  idle: '待机',
  wash: '清洗',
};

export const processCardStatusLabel: Record<ProcessCardStatus, string> = {
  draft: '草稿',
  published: '已发布',
  obsolete: '已作废',
};
