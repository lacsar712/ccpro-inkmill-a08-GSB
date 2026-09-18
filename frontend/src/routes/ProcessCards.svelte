<script lang="ts">
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { api } from '../lib/api';
  import { processCardStatusLabel } from '../lib/labels';
  import { processCardMillId } from '../lib/nav';
  import type { Mill, ProcessCard } from '../lib/types';

  let rows: ProcessCard[] = [];
  let mills: Mill[] = [];
  let error = '';
  let editingId: number | null = null;
  let selectedMillId = '';

  let form = {
    millId: '',
    versionNo: '1',
    content: '',
  };

  async function loadMills() {
    mills = await api<Mill[]>('/mills');
    const preselected = get(processCardMillId);
    if (preselected && mills.some((m) => m.id === preselected)) {
      selectedMillId = String(preselected);
    } else if (!selectedMillId && mills[0]) {
      selectedMillId = String(mills[0].id);
    }
    processCardMillId.set(null);
  }

  async function loadCards() {
    if (!selectedMillId) {
      rows = [];
      return;
    }
    rows = await api<ProcessCard[]>(`/process-cards?millId=${selectedMillId}`);
  }

  async function load() {
    error = '';
    try {
      await loadMills();
      if (!form.millId) form.millId = selectedMillId;
      await loadCards();
    } catch (e) {
      error = e instanceof Error ? e.message : '加载失败';
    }
  }

  onMount(load);

  async function switchMill() {
    error = '';
    if (!editingId) form.millId = selectedMillId;
    try {
      await loadCards();
      if (!editingId) form.versionNo = nextVersionNo();
    } catch (e) {
      error = e instanceof Error ? e.message : '加载失败';
    }
  }

  function millLabel(id: number): string {
    const m = mills.find((x) => x.id === id);
    return m ? `${m.millCode} (#${m.id})` : `#${id}`;
  }

  function nextVersionNo(): string {
    const max = rows.reduce((acc, r) => Math.max(acc, r.versionNo), 0);
    return String(max + 1);
  }

  function reset() {
    form = {
      millId: selectedMillId,
      versionNo: nextVersionNo(),
      content: '',
    };
    editingId = null;
  }

  function edit(row: ProcessCard) {
    editingId = row.id;
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
      selectedMillId = form.millId;
      await loadCards();
      reset();
    } catch (e) {
      error = e instanceof Error ? e.message : '保存失败';
    }
  }

  async function publish(row: ProcessCard) {
    if (!confirm(`确认发布 ${millLabel(row.millId)} 的 V${row.versionNo}？当前已发布版本将作废。`))
      return;
    error = '';
    try {
      await api(`/process-cards/${row.id}/publish`, { method: 'POST' });
      await loadCards();
    } catch (e) {
      error = e instanceof Error ? e.message : '发布失败';
    }
  }

  async function remove(id: number) {
    if (!confirm('确认删除该工艺卡版本？')) return;
    error = '';
    try {
      await api(`/process-cards/${id}`, { method: 'DELETE' });
      if (editingId === id) reset();
      await loadCards();
    } catch (e) {
      error = e instanceof Error ? e.message : '删除失败';
    }
  }
</script>

<header class="page-head">
  <h1>工艺卡</h1>
  <p>版本号同机唯一；同一研磨机最多一个已发布版本，发布后旧版本自动作废</p>
</header>

{#if error}
  <div class="err">{error}</div>
{/if}

<section class="panel">
  <h2>选择研磨机</h2>
  <div class="fields">
    <div class="field">
      <label>研磨机
        <select bind:value={selectedMillId} on:change={switchMill}>
          {#each mills as m}
            <option value={String(m.id)}>{m.millCode} — {m.pigmentBase}</option>
          {/each}
        </select>
      </label>
    </div>
  </div>
</section>

<section class="panel">
  <h2>{editingId ? '编辑工艺卡' : '新增工艺卡'}</h2>
  <div class="fields">
    <div class="field">
      <label>研磨机
        <select bind:value={form.millId}>
          {#each mills as m}
            <option value={String(m.id)}>{m.millCode}</option>
          {/each}
        </select>
      </label>
    </div>
    <div class="field"><label>版本号<input type="number" min="1" step="1" bind:value={form.versionNo} /></label></div>
    <div class="field full">
      <label>工艺内容<textarea rows="4" bind:value={form.content} placeholder="介质、填充率、线速度、温度、目标粘度、遍数…"></textarea></label>
    </div>
  </div>
  <div class="actions">
    <button class="btn-primary" on:click={save}>{editingId ? '保存' : '创建(草稿)'}</button>
    {#if editingId}
      <button class="btn-ghost" on:click={reset}>取消</button>
    {/if}
  </div>
</section>

<section class="panel">
  <h2>版本列表 — {selectedMillId ? millLabel(Number(selectedMillId)) : '未选择'}</h2>
  <table class="data-table">
    <thead>
      <tr>
        <th>版本</th>
        <th>状态</th>
        <th>工艺内容</th>
        <th>创建时间</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr>
          <td>V{row.versionNo}</td>
          <td><span class="badge {row.status}">{processCardStatusLabel[row.status]}</span></td>
          <td class="content-cell">{row.content}</td>
          <td>{row.createdAt || '—'}</td>
          <td class="ops">
            {#if row.status !== 'published'}
              <button class="link-btn" on:click={() => publish(row)}>发布</button>
            {/if}
            <button class="link-btn" on:click={() => edit(row)}>编辑</button>
            <button class="link-btn danger" on:click={() => remove(row.id)}>删除</button>
          </td>
        </tr>
      {:else}
        <tr><td colspan="5">暂无工艺卡版本</td></tr>
      {/each}
    </tbody>
  </table>
</section>

<style>
  .content-cell {
    max-width: 32rem;
    white-space: pre-wrap;
    word-break: break-word;
  }
</style>
