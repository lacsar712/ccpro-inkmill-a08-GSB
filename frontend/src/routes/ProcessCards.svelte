<script lang="ts">
  import { onMount } from 'svelte';
  import { createEventDispatcher } from 'svelte';
  import { api } from '../lib/api';
  import { processCardStatusLabel } from '../lib/labels';
  import type { Mill, ProcessCard, ProcessCardStatus } from '../lib/types';

  /* 由“研磨机”页跳转时携带机台 id；null 表示全部机台 */
  export let millFilter: number | null = null;

  const dispatch = createEventDispatcher<{ millchange: number | null }>();

  let rows: ProcessCard[] = [];
  let mills: Mill[] = [];
  let error = '';
  let editingId: number | null = null;
  let readonlyView = false;

  let form = {
    millId: '',
    versionNo: '1',
    content: '',
  };

  async function loadMills() {
    mills = await api<Mill[]>('/mills');
    if (!form.millId && mills[0]) form.millId = String(mills[0].id);
  }

  async function loadCards() {
    error = '';
    try {
      const qs = millFilter ? `?millId=${millFilter}` : '';
      rows = await api<ProcessCard[]>(`/process-cards${qs}`);
      // 新建表单跟随当前机台筛选，并预填下一个可用版本号
      if (!editingId && millFilter && Number(form.millId) !== millFilter) {
        form.millId = String(millFilter);
        form.versionNo = nextVersionNo(millFilter);
      }
    } catch (e) {
      error = e instanceof Error ? e.message : '加载失败';
    }
  }

  $: millFilter, loadCards();

  onMount(loadMills);

  function millLabel(id: number): string {
    const m = mills.find((x) => x.id === id);
    return m ? `${m.millCode} (#${m.id})` : `#${id}`;
  }

  function nextVersionNo(millId: number): string {
    const used = rows.filter((r) => r.millId === millId).map((r) => r.versionNo);
    return String((used.length ? Math.max(...used) : 0) + 1);
  }

  function onSelectMill() {
    if (!editingId && form.millId) form.versionNo = nextVersionNo(Number(form.millId));
  }

  function selectFilter(value: string) {
    millFilter = value ? Number(value) : null;
    dispatch('millchange', millFilter);
    reset();
  }

  function reset() {
    const target = millFilter || (mills[0] ? mills[0].id : 0);
    form = {
      millId: target ? String(target) : '',
      versionNo: target ? nextVersionNo(target) : '1',
      content: '',
    };
    editingId = null;
    readonlyView = false;
  }

  function edit(row: ProcessCard) {
    editingId = row.id;
    readonlyView = row.status !== 'draft';
    form = {
      millId: String(row.millId),
      versionNo: String(row.versionNo),
      content: row.content,
    };
  }

  async function save() {
    error = '';
    const payload = {
      millId: Number(form.millId),
      versionNo: Number(form.versionNo),
      content: form.content,
    };
    try {
      if (editingId) {
        await api(`/process-cards/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
      } else {
        await api('/process-cards', { method: 'POST', body: JSON.stringify(payload) });
      }
      reset();
      await loadCards();
    } catch (e) {
      error = e instanceof Error ? e.message : '保存失败';
    }
  }

  async function publish(row: ProcessCard) {
    if (!confirm(`确认发布 ${millLabel(row.millId)} 的 v${row.versionNo}？同一机台原已发布版本将自动作废。`)) return;
    error = '';
    try {
      await api(`/process-cards/${row.id}/publish`, { method: 'POST' });
      if (editingId === row.id) reset();
      await loadCards();
    } catch (e) {
      error = e instanceof Error ? e.message : '发布失败';
    }
  }

  async function remove(row: ProcessCard) {
    if (!confirm('确认删除该草稿工艺卡？')) return;
    error = '';
    try {
      await api(`/process-cards/${row.id}`, { method: 'DELETE' });
      if (editingId === row.id) reset();
      await loadCards();
    } catch (e) {
      error = e instanceof Error ? e.message : '删除失败';
    }
  }

  const statusOrder: Record<ProcessCardStatus, number> = {
    published: 0,
    draft: 1,
    obsolete: 2,
  };

  $: sortedRows = [...rows].sort(
    (a, b) =>
      a.millId - b.millId ||
      statusOrder[a.status] - statusOrder[b.status] ||
      b.versionNo - a.versionNo,
  );
</script>

<header class="page-head">
  <h1>研磨工艺卡</h1>
  <p>工艺卡挂在研磨机下，版本号同机唯一；发布新版本时旧版本自动作废</p>
</header>

{#if error}
  <div class="err">{error}</div>
{/if}

<section class="panel">
  <div class="filter-bar">
    <label>机台筛选
      <select value={millFilter === null ? '' : String(millFilter)} on:change={(e) => selectFilter(e.currentTarget.value)}>
        <option value="">全部机台</option>
        {#each mills as m}
          <option value={String(m.id)}>{m.millCode} (#{m.id})</option>
        {/each}
      </select>
    </label>
  </div>
</section>

<section class="panel">
  <h2>
    {#if readonlyView}查看工艺卡（仅草稿可编辑）{:else if editingId}编辑草稿 v{form.versionNo}{:else}新增工艺卡（草稿）{/if}
  </h2>
  <div class="fields">
    <div class="field">
      <label>研磨机
        <select bind:value={form.millId} on:change={onSelectMill} disabled={readonlyView}>
          {#each mills as m}
            <option value={String(m.id)}>{m.millCode} (#{m.id})</option>
          {/each}
        </select>
      </label>
    </div>
    <div class="field">
      <label>版本号（正整数，同机唯一）
        <input type="number" min="1" step="1" bind:value={form.versionNo} disabled={readonlyView} />
      </label>
    </div>
    <div class="field full">
      <label>工艺内容
        <textarea rows="7" bind:value={form.content} disabled={readonlyView} placeholder="研磨介质、遍次、温度/粘度控制、细度要求……"></textarea>
      </label>
    </div>
  </div>
  {#if !readonlyView}
    <div class="actions">
      <button class="btn-primary" on:click={save}>{editingId ? '保存' : '创建草稿'}</button>
      {#if editingId}
        <button class="btn-ghost" on:click={reset}>取消</button>
      {/if}
    </div>
  {:else}
    <div class="actions">
      <button class="btn-ghost" on:click={reset}>返回新增</button>
    </div>
  {/if}
</section>

<section class="panel">
  <table class="data-table">
    <thead>
      <tr>
        <th>研磨机</th>
        <th>版本</th>
        <th>状态</th>
        <th>创建时间</th>
        <th>工艺内容</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each sortedRows as row}
        <tr class:row-published={row.status === 'published'}>
          <td>{millLabel(row.millId)}</td>
          <td>v{row.versionNo}</td>
          <td><span class="card-badge {row.status}">{processCardStatusLabel[row.status]}</span></td>
          <td class="muted">{row.createdAt}</td>
          <td><pre class="content">{row.content}</pre></td>
          <td class="ops">
            {#if row.status === 'draft'}
              <button class="link-btn" on:click={() => edit(row)}>编辑</button>
              <button class="link-btn publish" on:click={() => publish(row)}>发布</button>
              <button class="link-btn danger" on:click={() => remove(row)}>删除</button>
            {:else}
              <button class="link-btn" on:click={() => edit(row)}>查看</button>
            {/if}
          </td>
        </tr>
      {:else}
        <tr><td colspan="6">暂无工艺卡</td></tr>
      {/each}
    </tbody>
  </table>
</section>

<style>
  .filter-bar label {
    display: inline-grid;
    gap: 0.3rem;
    font-size: 0.8rem;
    color: var(--steel);
    min-width: 240px;
  }

  .filter-bar select {
    border: 1px solid var(--line);
    background: rgba(0, 0, 0, 0.35);
    color: white;
    padding: 0.55rem 0.65rem;
  }

  textarea {
    resize: vertical;
    line-height: 1.55;
  }

  .content {
    margin: 0;
    max-width: 460px;
    max-height: 6.2em;
    overflow: hidden;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: var(--font-body);
    font-size: 0.85rem;
    color: var(--mist);
    mask-image: linear-gradient(180deg, black 65%, transparent 100%);
  }

  .card-badge {
    display: inline-block;
    padding: 0.15rem 0.45rem;
    font-size: 0.75rem;
    border: 1px solid var(--line);
    border-radius: 2px;
  }

  .card-badge.published {
    border-color: var(--ok);
    color: var(--ok);
  }

  .card-badge.draft {
    border-color: var(--vermillion-700);
    color: var(--vermillion-400);
  }

  .card-badge.obsolete {
    color: var(--steel);
    opacity: 0.75;
  }

  tr.row-published td {
    background: rgba(61, 154, 106, 0.07);
  }

  .link-btn.publish {
    color: var(--ok);
  }
</style>
