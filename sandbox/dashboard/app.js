const byId = id => document.getElementById(id);
const put = (id, text) => { byId(id).textContent = text; };
const clock = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
});
const day = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit',
});
const number = new Intl.NumberFormat('zh-CN');
let selected;
let reading = false;
let data;
let signature;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function format(value, formatter) {
  const date = new Date(value ?? NaN);
  return Number.isFinite(date.getTime()) ? formatter.format(date) : '—';
}

function statusOf(run) {
  if (run.state === 'complete') return '已完成';
  if (run.state === 'failed') return '失败';
  const elapsed = Date.parse(data.now) - Date.parse(run.start);
  return run.state === 'started' && data.vm === true && elapsed >= 0 && elapsed < 30 * 60_000
    ? '进行中' : '缺少结束记录';
}

function titleOf(run) {
  const text = run.summary.trim().replace(/\s+/g, ' ');
  if (text.length > 86) return text.slice(0, 86) + '…';
  return text || (run.turn ? `第 ${run.turn} 轮` : statusOf(run));
}

function usageOf(usage) {
  const fields = [['inputTokens', '输入'], ['outputTokens', '输出'],
    ['cacheReadTokens', '缓存读取'], ['cacheWriteTokens', '缓存写入']];
  return fields.filter(([key]) => key in usage)
    .map(([key, label]) => `${label} ${number.format(usage[key])}`).join(' · ');
}

function durationOf(run) {
  const seconds = Math.round((Date.parse(run.end) - Date.parse(run.start)) / 1000);
  if (!Number.isFinite(seconds) || seconds < 0) return '';
  if (seconds < 60) return `${seconds} 秒`;
  return `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`;
}

async function detail(run, body) {
  body.replaceChildren(element('p', 'detail-meta', '加载本轮记录…'));
  try {
    const response = await fetch('/api/runs/' + run.id);
    if (!response.ok) throw new Error('detail');
    const record = await response.json();
    const meta = [
      `开始 ${format(record.start, clock)}`,
      record.end && `结束 ${format(record.end, clock)}`,
      durationOf(record),
      record.toolCount ? `${record.toolCount} 次工具调用` : '',
      usageOf(record.usage),
    ].filter(Boolean);
    body.replaceChildren(element('p', 'detail-meta', meta.join(' · ')));
    const list = element('ol', 'events');
    for (const event of record.events) {
      const item = element('li');
      item.append(element('time', '', format(event.time, clock)), element('strong', '', event.title));
      if (event.text) item.append(element('pre', '', event.text));
      list.append(item);
    }
    if (record.events.length) {
      body.append(element('h3', '', '操作和结果'), list);
    }
    if (record.eventCount > record.events.length) {
      body.append(element('p', 'detail-meta', `显示最近 ${record.events.length} 条操作`));
    }
    return true;
  } catch {
    body.replaceChildren(element('p', 'detail-meta', '这轮记录无法读取。折叠后重新展开即可重试。'));
    return false;
  }
}

function runRow(run, opened) {
  const row = element('details', 'run');
  row.dataset.id = run.id;
  const header = element('summary');
  const stamp = run.start || run.last;
  const time = element('time', '', format(stamp, clock));
  time.dateTime = stamp;
  time.title = format(stamp, day);
  const state = element('span', 'run-meta', statusOf(run));
  state.dataset.state = run.state;
  const chevron = element('span', 'chevron');
  chevron.setAttribute('aria-hidden', 'true');
  header.append(time, element('span', 'run-title', titleOf(run)), state, chevron);
  const body = element('div', 'run-body');
  row.append(header, body);
  let loaded = false;
  let loading = false;
  row.addEventListener('toggle', async () => {
    if (!row.open || loaded || loading) return;
    loading = true;
    loaded = await detail(run, body);
    loading = false;
  });
  row.open = opened;
  return row;
}

function renderRuns() {
  const formal = data.runs.filter(row => row.mode === 'experiment');
  const tests = data.runs.length - formal.length;
  selected ??= formal.length || !tests ? 'experiment' : 'test';
  const rows = data.runs.filter(row => row.mode === selected);
  put('experiment-count', formal.length);
  put('test-count', tests);
  for (const button of document.querySelectorAll('[data-mode]')) {
    button.setAttribute('aria-pressed', String(button.dataset.mode === selected));
  }
  const nextSignature = JSON.stringify([selected, rows, rows.map(statusOf)]);
  if (signature === nextSignature) return;
  signature = nextSignature;
  const opened = new Set(Array.from(document.querySelectorAll('.run[open]'), row => row.dataset.id));
  if (!rows.length) {
    byId('runs').replaceChildren(element('p', 'empty', selected === 'experiment'
      ? '暂无正式运行记录。' : '暂无验收记录。'));
    return;
  }
  let previousDay;
  const content = [];
  for (const run of rows) {
    const group = format(run.start || run.last, day);
    if (group !== previousDay) {
      content.push(element('p', 'day', group));
      previousDay = group;
    }
    content.push(runRow(run, opened.has(run.id)));
  }
  byId('runs').replaceChildren(...content);
}

function render() {
  const latest = data.runs.find(run => run.mode === 'experiment');
  put('instance', data.name);
  put('clock', format(data.now, clock));
  put('overview', latest ? `最近一次正式运行 · ${format(latest.start || latest.last, day)}`
    : '正式实验尚无运行记录');
  put('vm', data.vm === true ? '运行中' : data.vm === false ? '已关机' : '状态未知');
  put('timer', data.timer.state === 'enabled' ? '已启用'
    : data.timer.state === 'disabled' ? '未启用' : '待核验');
  put('timer-note', data.timer.checked ? `${format(data.timer.checked, day)} ${format(data.timer.checked, clock)} 核验`
    : '等待管理端状态记录');
  put('last', latest ? statusOf(latest) : '待开始');
  put('last-note', latest ? `${format(latest.start || latest.last, day)} ${format(latest.start || latest.last, clock)}` : '正式实验');
  put('disk', data.allocated == null ? '未知' : `${(data.allocated / 2**30).toFixed(1)} GiB`);
  put('disk-note', data.capacity ? `${data.capacity} GB 虚拟容量` : '虚拟磁盘');
  const next = format(data.calendarNext, clock);
  const plan = `${format(data.calendarNext, day)} ${next}`;
  const scheduled = data.vm === true && data.timer.state === 'enabled';
  put('schedule-note', scheduled ? `按最近核验推算，下一个时段 ${plan}` : `下一个计划时段 ${plan}`);
  byId('slots').replaceChildren(...data.hours.map(hour => {
    const text = `${String(hour).padStart(2, '0')}:00`;
    return element('li', text === next ? 'next' : '', text);
  }));
  put('log-size', `${number.format(Math.round(data.logBytes / 1024))} KiB`);
  put('rotated', data.rotated ? '已保留' : '暂无');
  put('checked', format(data.now, clock));
}

async function refresh() {
  if (reading) return;
  reading = true;
  byId('refresh').disabled = true;
  const notice = byId('notice');
  try {
    const response = await fetch('/api/status');
    if (!response.ok) throw new Error('status');
    data = await response.json();
    render();
    renderRuns();
    notice.hidden = !data.skipped;
    if (data.skipped) notice.textContent = `有 ${data.skipped} 条审计记录无法解析。`;
  } catch {
    notice.hidden = false;
    notice.textContent = '暂时无法读取宿主状态。可点击刷新重试。';
  } finally {
    reading = false;
    byId('refresh').disabled = false;
  }
}

for (const button of document.querySelectorAll('[data-mode]')) {
  button.addEventListener('click', () => {
    selected = button.dataset.mode;
    if (data) renderRuns();
  });
}
byId('refresh').addEventListener('click', refresh);
refresh();
setInterval(refresh, 12000);
