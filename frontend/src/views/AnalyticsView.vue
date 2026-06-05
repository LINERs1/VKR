<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import { apiFetch } from '../api'
import GlassHeader from '../components/GlassHeader.vue'
import {
  Chart,
  LineController, BarController, DoughnutController,
  LineElement, BarElement, ArcElement, PointElement,
  CategoryScale, LinearScale,
  Tooltip, Legend, Filler,
} from 'chart.js'

Chart.register(
  LineController, BarController, DoughnutController,
  LineElement, BarElement, ArcElement, PointElement,
  CategoryScale, LinearScale,
  Tooltip, Legend, Filler,
)

const router = useRouter()
const { fetchUser } = useAuth()

const data = ref(null)
const loading = ref(true)
const error = ref('')
const activeTab = ref('overview')
const periodDays = ref(30)

// Chart canvas refs
const activityChartRef = ref(null)
const perfChartRef = ref(null)
const hwChartRef = ref(null)
const gradeChartRef = ref(null)
const weakTopicsChartRef = ref(null)
const studentActivityChartRef = ref(null)

let charts = {}

function destroyChart(key) {
  if (charts[key]) {
    charts[key].destroy()
    delete charts[key]
  }
}

function destroyAll() {
  Object.keys(charts).forEach(k => destroyChart(k))
}

function shortDate(dateStr) {
  const d = new Date(dateStr)
  return `${d.getDate()}.${d.getMonth() + 1}`
}

function fmtMs(ms) {
  if (ms == null) return '—'
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)} с`
  return `${Math.round(ms)} мс`
}

const CHART_DEFAULTS = {
  color: '#f0f0f5',
  font: { family: 'Inter, system-ui, sans-serif', size: 12 },
}

Chart.defaults.color = CHART_DEFAULTS.color
Chart.defaults.font = CHART_DEFAULTS.font

function chartColors() {
  return {
    indigo:       'rgba(99, 102, 241, 0.85)',
    indigoBg:     'rgba(99, 102, 241, 0.15)',
    emerald:      'rgba(16, 185, 129, 0.85)',
    emeraldBg:    'rgba(16, 185, 129, 0.12)',
    amber:        'rgba(245, 158, 11, 0.85)',
    amberBg:      'rgba(245, 158, 11, 0.12)',
    rose:         'rgba(239, 68, 68, 0.8)',
    roseBg:       'rgba(239, 68, 68, 0.1)',
    grid:         'rgba(255, 255, 255, 0.06)',
    tick:         '#55556a',
  }
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    data.value = await apiFetch(`/analytics/detailed?days=${periodDays.value}`)
  } catch (e) {
    error.value = e.message || 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

async function renderCharts() {
  await nextTick()
  const d = data.value
  if (!d) return
  const c = chartColors()

  // ── Tab: overview — Activity chart ─────────────────────────
  if (activeTab.value === 'overview' && activityChartRef.value) {
    destroyChart('activity')
    const labels = d.daily_events.map(x => shortDate(x.date))
    charts.activity = new Chart(activityChartRef.value, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Всего событий',
            data: d.daily_events.map(x => x.total),
            borderColor: c.indigo,
            backgroundColor: c.indigoBg,
            fill: true,
            tension: 0.4,
            pointRadius: 3,
            pointHoverRadius: 5,
          },
          {
            label: 'Запросы к чату',
            data: d.daily_events.map(x => x.chat),
            borderColor: c.emerald,
            backgroundColor: 'transparent',
            tension: 0.4,
            pointRadius: 3,
            pointHoverRadius: 5,
          },
          {
            label: 'Голос. навигация',
            data: d.daily_events.map(x => x.voice),
            borderColor: c.amber,
            backgroundColor: 'transparent',
            tension: 0.4,
            pointRadius: 3,
            pointHoverRadius: 5,
            borderDash: [4, 3],
          },
        ],
      },
      options: chartOptions('Активность ИИ по дням'),
    })
  }

  // ── Tab: ai — Performance chart ────────────────────────────
  if (activeTab.value === 'ai' && perfChartRef.value) {
    destroyChart('perf')
    const validPerf = d.perf_by_day.filter(x => x.llm_avg_ms != null || x.rag_avg_ms != null)
    const labels = validPerf.length > 0
      ? d.perf_by_day.map(x => shortDate(x.date))
      : d.perf_by_day.map(x => shortDate(x.date))
    charts.perf = new Chart(perfChartRef.value, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'LLM (мс)',
            data: d.perf_by_day.map(x => x.llm_avg_ms),
            borderColor: c.indigo,
            backgroundColor: c.indigoBg,
            fill: true,
            tension: 0.4,
            spanGaps: true,
            pointRadius: 3,
          },
          {
            label: 'RAG (мс)',
            data: d.perf_by_day.map(x => x.rag_avg_ms),
            borderColor: c.emerald,
            backgroundColor: 'transparent',
            tension: 0.4,
            spanGaps: true,
            pointRadius: 3,
          },
        ],
      },
      options: chartOptions('Среднее время ответа (мс)'),
    })
  }

  // ── Tab: homework — HW by day ──────────────────────────────
  if (activeTab.value === 'homework' && hwChartRef.value) {
    destroyChart('hw')
    charts.hw = new Chart(hwChartRef.value, {
      type: 'bar',
      data: {
        labels: d.hw_by_day.map(x => shortDate(x.date)),
        datasets: [
          {
            label: 'Сдано',
            data: d.hw_by_day.map(x => x.submitted),
            backgroundColor: c.indigo,
            borderRadius: 4,
          },
          {
            label: 'Проверено',
            data: d.hw_by_day.map(x => x.graded),
            backgroundColor: c.emerald,
            borderRadius: 4,
          },
        ],
      },
      options: {
        ...chartOptions('Домашние задания по дням'),
        scales: {
          x: {
            stacked: false,
            grid: { color: c.grid },
            ticks: { color: c.tick, maxTicksLimit: 10 },
          },
          y: {
            beginAtZero: true,
            grid: { color: c.grid },
            ticks: { color: c.tick, stepSize: 1 },
          },
        },
      },
    })

    // Grade distribution doughnut
    if (gradeChartRef.value && d.homework.grade_distribution && Object.keys(d.homework.grade_distribution).length > 0) {
      destroyChart('grade')
      const dist = d.homework.grade_distribution
      const keys = ['1', '2', '3', '4', '5']
      const gradePalette = [c.rose, c.amber, 'rgba(234,179,8,0.85)', c.emerald, 'rgba(99,102,241,0.85)']
      charts.grade = new Chart(gradeChartRef.value, {
        type: 'doughnut',
        data: {
          labels: keys.map(k => `Оценка ${k}`),
          datasets: [{
            data: keys.map(k => dist[k] || 0),
            backgroundColor: gradePalette,
            borderColor: 'transparent',
            borderWidth: 0,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'right', labels: { color: '#8b8b9e', font: { size: 12 }, padding: 12 } },
            tooltip: {
              callbacks: {
                label: ctx => ` ${ctx.label}: ${ctx.raw} раб.`,
              },
            },
          },
          cutout: '68%',
        },
      })
    }
  }

  // ── Tab: students ───────────────────────────────────────────
  if (activeTab.value === 'students') {
    if (weakTopicsChartRef.value && d.weak_topics.length > 0) {
      destroyChart('weakTopics')
      charts.weakTopics = new Chart(weakTopicsChartRef.value, {
        type: 'bar',
        data: {
          labels: d.weak_topics.map(t => t.topic.length > 22 ? t.topic.slice(0, 20) + '…' : t.topic),
          datasets: [
            {
              label: 'Всего ошибок',
              data: d.weak_topics.map(t => t.total_wrong),
              backgroundColor: c.rose,
              borderRadius: 4,
            },
            {
              label: 'Студентов',
              data: d.weak_topics.map(t => t.students_count),
              backgroundColor: c.amber,
              borderRadius: 4,
            },
          ],
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              beginAtZero: true,
              grid: { color: c.grid },
              ticks: { color: c.tick, stepSize: 1 },
            },
            y: {
              grid: { display: false },
              ticks: { color: '#8b8b9e', font: { size: 12 } },
            },
          },
          plugins: {
            legend: { labels: { color: '#8b8b9e' } },
            tooltip: { mode: 'index' },
          },
        },
      })
    }

    if (studentActivityChartRef.value && d.student_activity.length > 0) {
      destroyChart('studentActivity')
      const top10 = d.student_activity.slice(0, 10)
      charts.studentActivity = new Chart(studentActivityChartRef.value, {
        type: 'bar',
        data: {
          labels: top10.map(s => s.username),
          datasets: [{
            label: 'Сообщений к ИИ',
            data: top10.map(s => s.message_count),
            backgroundColor: top10.map((_, i) => i === 0 ? c.indigo : i === 1 ? 'rgba(99,102,241,0.65)' : 'rgba(99,102,241,0.4)'),
            borderRadius: 5,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              grid: { display: false },
              ticks: { color: '#8b8b9e' },
            },
            y: {
              beginAtZero: true,
              grid: { color: c.grid },
              ticks: { color: c.tick, stepSize: 1 },
            },
          },
          plugins: {
            legend: { display: false },
          },
        },
      })
    }
  }
}

function chartOptions(title) {
  const c = chartColors()
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        labels: { color: '#8b8b9e', usePointStyle: true, pointStyleWidth: 8, padding: 16 },
      },
      tooltip: {
        backgroundColor: '#18181d',
        borderColor: 'rgba(255,255,255,0.1)',
        borderWidth: 1,
        titleColor: '#f0f0f5',
        bodyColor: '#8b8b9e',
        padding: 10,
      },
    },
    scales: {
      x: {
        grid: { color: c.grid },
        ticks: { color: c.tick, maxTicksLimit: 12 },
      },
      y: {
        beginAtZero: true,
        grid: { color: c.grid },
        ticks: { color: c.tick },
      },
    },
  }
}

watch([activeTab, data], () => {
  destroyAll()
  renderCharts()
}, { flush: 'post' })

watch(periodDays, () => loadData())

onMounted(async () => {
  const user = await fetchUser()
  if (!user || user.role !== 'teacher') {
    router.push('/homeworks')
    return
  }
  await loadData()
  await renderCharts()
})
</script>

<template>
  <div class="analytics-page">
    <!-- Header -->
    <GlassHeader>
      <div style="display: flex; align-items: center; gap: 16px;">
        <button class="glass-back-btn" @click="router.push('/journal')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="19" y1="12" x2="5" y2="12"/>
            <polyline points="12 19 5 12 12 5"/>
          </svg>
          Журнал
        </button>
        <div style="width:1px; height:24px; background:rgba(255,255,255,0.1);"></div>
        <div style="display: flex; align-items: center; gap: 12px;">
          <h1 class="glass-title">Аналитика</h1>
          <span style="font-size: 13px; color: var(--text-secondary);">Детальная статистика</span>
        </div>
      </div>
      <div style="display: flex; align-items: center; gap: 12px;">
        <div class="animated-period-selector">
          <div class="period-active-pill" :style="{ transform: `translateX(${[7, 14, 30, 90].indexOf(periodDays) * 100}%)` }"></div>
          <button
            v-for="d in [7, 14, 30, 90]" :key="d"
            class="period-btn"
            :class="{ active: periodDays === d }"
            @click="periodDays = d"
          >{{ d }}д</button>
        </div>
        <button class="glass-btn" @click="loadData" :disabled="loading" title="Обновить" style="padding: 8px;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" :class="{ spinning: loading }">
            <polyline points="23 4 23 10 17 10"/>
            <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
          </svg>
        </button>
      </div>
    </GlassHeader>

    <!-- Error state -->
    <div v-if="error" class="error-state">
      <div class="error-icon">⚠️</div>
      <div>
        <div class="error-title">Не удалось загрузить данные</div>
        <div class="error-msg">{{ error }}</div>
      </div>
      <button class="btn-retry" @click="loadData">Повторить</button>
    </div>

    <template v-if="!error">
      <!-- Summary KPIs -->
      <div class="kpi-row" v-if="data && !loading">
        <div class="kpi-card">
          <div class="kpi-label">Событий ИИ</div>
          <div class="kpi-value">{{ data.summary.total_ai_events.toLocaleString() }}</div>
          <div class="kpi-sub">за {{ data.period_days }} дней</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Запросов к чату</div>
          <div class="kpi-value">{{ data.summary.total_chat_queries.toLocaleString() }}</div>
          <div class="kpi-sub">RAG-поисков</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">ДЗ сдано</div>
          <div class="kpi-value">{{ data.summary.total_hw_submitted }}</div>
          <div class="kpi-sub">проверено: {{ data.summary.total_hw_graded }}</div>
        </div>
        <div class="kpi-card" v-if="data.summary.avg_grade != null">
          <div class="kpi-label">Средняя оценка</div>
          <div class="kpi-value grade-val">{{ data.summary.avg_grade }}</div>
          <div class="kpi-sub">из 5 баллов</div>
        </div>
        <div class="kpi-card" v-if="data.summary.voice_success_rate != null">
          <div class="kpi-label">Навигация (голос)</div>
          <div class="kpi-value">{{ Math.round(data.summary.voice_success_rate * 100) }}%</div>
          <div class="kpi-sub">успешных переходов</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Активных студентов</div>
          <div class="kpi-value">{{ data.summary.active_students }}</div>
          <div class="kpi-sub">за период</div>
        </div>
      </div>

      <!-- KPI skeleton -->
      <div class="kpi-row" v-else-if="loading">
        <div class="kpi-card skeleton" v-for="i in 6" :key="i"></div>
      </div>

      <!-- Tabs -->
      <div class="tabs-bar">
        <button
          v-for="tab in [
            { id: 'overview', label: 'Обзор' },
            { id: 'ai',       label: 'ИИ & Производительность' },
            { id: 'homework', label: 'Домашние задания' },
            { id: 'students', label: 'Студенты' },
          ]"
          :key="tab.id"
          class="tab-btn"
          :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >{{ tab.label }}</button>
      </div>

      <!-- Loading state -->
      <div class="chart-loading" v-if="loading">
        <div class="chart-spinner"></div>
        <span>Загрузка данных...</span>
      </div>

      <!-- ── Tab: Overview ─────────────────────────────────── -->
      <div v-if="!loading && data && activeTab === 'overview'" class="tab-content">
        <div class="chart-block full">
          <div class="chart-header">
            <div class="chart-title">Активность ИИ по дням</div>
            <div class="chart-desc">Количество событий: чат, голосовая навигация, суммарно</div>
          </div>
          <div class="chart-area h300">
            <canvas ref="activityChartRef"></canvas>
          </div>
        </div>

        <div class="metrics-summary-grid">
          <div class="metric-tile">
            <div class="mt-icon indigo">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
              </svg>
            </div>
            <div class="mt-content">
              <div class="mt-label">RAG-поиск (среднее)</div>
              <div class="mt-value">{{ fmtMs(data.summary && data.perf_by_day && data.perf_by_day.reduce((a, x) => x.rag_avg_ms ? [...a, x.rag_avg_ms] : a, []).length ? data.perf_by_day.reduce((a, x) => x.rag_avg_ms ? [...a, x.rag_avg_ms] : a, []).reduce((s, v) => s + v, 0) / data.perf_by_day.reduce((a, x) => x.rag_avg_ms ? [...a, x.rag_avg_ms] : a, []).length : null) }}</div>
            </div>
          </div>
          <div class="metric-tile">
            <div class="mt-icon emerald">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
              </svg>
            </div>
            <div class="mt-content">
              <div class="mt-label">Голосовых навигаций</div>
              <div class="mt-value">{{ data.summary.total_voice_navigations }}</div>
            </div>
          </div>
          <div class="metric-tile">
            <div class="mt-icon amber">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
            </div>
            <div class="mt-content">
              <div class="mt-label">Слабых тем выявлено</div>
              <div class="mt-value">{{ data.weak_topics.length }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Tab: AI Performance ────────────────────────────── -->
      <div v-if="!loading && data && activeTab === 'ai'" class="tab-content">
        <div class="chart-block full">
          <div class="chart-header">
            <div class="chart-title">Время ответа LLM и RAG</div>
            <div class="chart-desc">Среднее время генерации ответа и векторного поиска по дням (мс)</div>
          </div>
          <div class="chart-area h300">
            <canvas ref="perfChartRef"></canvas>
          </div>
        </div>

        <div class="info-cards">
          <div class="info-card" v-if="data.perf_by_day.some(x => x.llm_avg_ms != null)">
            <div class="ic-title">LLM — генерация ответа</div>
            <div class="ic-stats">
              <div class="ic-stat">
                <span class="ic-lbl">Минимум</span>
                <span class="ic-val">{{ fmtMs(Math.min(...data.perf_by_day.filter(x => x.llm_avg_ms).map(x => x.llm_avg_ms))) }}</span>
              </div>
              <div class="ic-stat">
                <span class="ic-lbl">Максимум</span>
                <span class="ic-val">{{ fmtMs(Math.max(...data.perf_by_day.filter(x => x.llm_avg_ms).map(x => x.llm_avg_ms))) }}</span>
              </div>
              <div class="ic-stat">
                <span class="ic-lbl">Среднее</span>
                <span class="ic-val">{{ fmtMs(data.perf_by_day.filter(x => x.llm_avg_ms).reduce((s, x) => s + x.llm_avg_ms, 0) / (data.perf_by_day.filter(x => x.llm_avg_ms).length || 1)) }}</span>
              </div>
            </div>
          </div>
          <div class="info-card empty-state" v-else>
            <div class="es-icon">📊</div>
            <div>Нет данных о производительности LLM за выбранный период</div>
          </div>

          <div class="info-card">
            <div class="ic-title">Навигация голосом</div>
            <div class="nav-stats">
              <div class="nav-bar-wrap">
                <div class="nav-bar-track">
                  <div
                    class="nav-bar-fill"
                    :style="{ width: (data.summary.voice_success_rate != null ? data.summary.voice_success_rate * 100 : 0) + '%' }"
                  ></div>
                </div>
                <span class="nav-pct">{{ data.summary.voice_success_rate != null ? Math.round(data.summary.voice_success_rate * 100) + '%' : '—' }}</span>
              </div>
              <div class="nav-legend">
                <span class="nav-ok">Успешно: {{ data.summary.total_voice_navigations > 0 ? Math.round(data.summary.voice_success_rate * data.summary.total_voice_navigations) : 0 }}</span>
                <span class="nav-fail">Всего: {{ data.summary.total_voice_navigations }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Tab: Homework ──────────────────────────────────── -->
      <div v-if="!loading && data && activeTab === 'homework'" class="tab-content">
        <div class="hw-top">
          <div class="chart-block flex-1">
            <div class="chart-header">
              <div class="chart-title">ДЗ по дням</div>
              <div class="chart-desc">Сданные и проверенные работы</div>
            </div>
            <div class="chart-area h260">
              <canvas ref="hwChartRef"></canvas>
            </div>
          </div>

          <div class="chart-block w280" v-if="data.homework.grade_distribution && Object.keys(data.homework.grade_distribution).length">
            <div class="chart-header">
              <div class="chart-title">Оценки</div>
              <div class="chart-desc">Распределение по баллам</div>
            </div>
            <div class="chart-area h260">
              <canvas ref="gradeChartRef"></canvas>
            </div>
          </div>
        </div>

        <div class="hw-stats-grid">
          <div class="hw-stat">
            <div class="hs-label">Всего ДЗ</div>
            <div class="hs-val">{{ data.homework.total }}</div>
          </div>
          <div class="hw-stat">
            <div class="hs-label">Сдано</div>
            <div class="hs-val emerald">{{ data.homework.submitted }}</div>
          </div>
          <div class="hw-stat">
            <div class="hs-label">Проверено</div>
            <div class="hs-val indigo">{{ data.homework.graded }}</div>
          </div>
          <div class="hw-stat">
            <div class="hs-label">Средняя оценка</div>
            <div class="hs-val amber">{{ data.homework.avg_grade != null ? data.homework.avg_grade : '—' }}</div>
          </div>
          <div class="hw-stat">
            <div class="hs-label">Процент сдачи</div>
            <div class="hs-val">
              {{ data.homework.total > 0 ? Math.round(data.homework.submitted / data.homework.total * 100) : 0 }}%
            </div>
          </div>
        </div>
      </div>

      <!-- ── Tab: Students ──────────────────────────────────── -->
      <div v-if="!loading && data && activeTab === 'students'" class="tab-content">
        <div class="students-grid">
          <div class="chart-block flex-1" v-if="data.student_activity.length > 0">
            <div class="chart-header">
              <div class="chart-title">Топ-10 активных студентов</div>
              <div class="chart-desc">Количество сообщений к ИИ-ассистенту за период</div>
            </div>
            <div class="chart-area h280">
              <canvas ref="studentActivityChartRef"></canvas>
            </div>
          </div>
          <div class="empty-state-box" v-else>
            <div class="es-icon">👥</div>
            <div class="es-title">Нет данных об активности</div>
            <div class="es-desc">Студенты ещё не делали запросов к ИИ за выбранный период</div>
          </div>

          <div class="chart-block flex-1" v-if="data.weak_topics.length > 0">
            <div class="chart-header">
              <div class="chart-title">Слабые темы</div>
              <div class="chart-desc">Темы с наибольшим количеством ошибок по всем студентам</div>
            </div>
            <div class="chart-area" :style="{ height: Math.max(200, data.weak_topics.length * 38) + 'px' }">
              <canvas ref="weakTopicsChartRef"></canvas>
            </div>
          </div>
          <div class="empty-state-box" v-else>
            <div class="es-icon">✅</div>
            <div class="es-title">Слабых тем не обнаружено</div>
            <div class="es-desc">Система не зафиксировала повторяющихся ошибок</div>
          </div>
        </div>

        <!-- Student table -->
        <div class="student-table-wrap" v-if="data.student_activity.length > 0">
          <div class="chart-header" style="margin-bottom: 12px;">
            <div class="chart-title">Детализация по студентам</div>
          </div>
          <table class="student-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Студент</th>
                <th>Сообщений к ИИ</th>
                <th>Последняя активность</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(s, idx) in data.student_activity" :key="s.username">
                <td class="td-idx">{{ idx + 1 }}</td>
                <td class="td-name">{{ s.username }}</td>
                <td class="td-count">
                  <div class="count-bar-wrap">
                    <div class="count-bar" :style="{ width: (s.message_count / (data.student_activity[0]?.message_count || 1) * 100) + '%' }"></div>
                    <span>{{ s.message_count }}</span>
                  </div>
                </td>
                <td class="td-date">{{ s.last_active ? s.last_active.split('T')[0] : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.analytics-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px 80px;
  font-family: 'Inter', system-ui, sans-serif;
}

.animated-period-selector {
  position: relative;
  display: flex;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 40px;
  padding: 2px;
  width: 176px;
}
.period-active-pill {
  position: absolute;
  top: 2px;
  left: 2px;
  width: calc(25% - 1px);
  height: calc(100% - 4px);
  background: rgba(255, 255, 255, 0.15);
  border-radius: 40px;
  transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.period-btn {
  flex: 1;
  position: relative;
  z-index: 1;
  padding: 6px 0;
  text-align: center;
  font-size: 13px;
  font-weight: 500;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  border-radius: 40px;
  cursor: pointer;
  font-family: inherit;
  transition: color 0.2s ease;
}
.period-btn.active { color: var(--text); }
.period-btn:hover:not(.active) { color: var(--text); }.refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.spinning { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Error state ────────────────────────────── */
.error-state {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--danger-subtle);
  border: 1px solid rgba(239,68,68,0.2);
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 20px;
}
.error-icon { font-size: 20px; }
.error-title { font-size: 14px; font-weight: 600; color: var(--danger); }
.error-msg   { font-size: 13px; color: var(--text-secondary); margin-top: 2px; }
.btn-retry {
  margin-left: auto;
  padding: 6px 14px;
  background: var(--danger);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
}

/* ── KPI row ────────────────────────────────── */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.kpi-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px 18px;
  transition: border-color 0.15s;
}
.kpi-card:hover { border-color: var(--border-light); }

.kpi-label { font-size: 12px; color: var(--text-secondary); font-weight: 500; margin-bottom: 8px; }
.kpi-value { font-size: 28px; font-weight: 800; letter-spacing: -0.025em; color: var(--text); line-height: 1; }
.kpi-value.grade-val { color: #fbbf24; }
.kpi-sub   { font-size: 12px; color: var(--text-muted); margin-top: 5px; }

.kpi-card.skeleton {
  height: 90px;
  background: linear-gradient(90deg, var(--card) 25%, var(--bg-elevated) 50%, var(--card) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer { to { background-position: -200% 0; } }

/* ── Tabs ───────────────────────────────────── */
.tabs-bar {
  display: flex;
  gap: 2px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 24px;
  overflow-x: auto;
}

.tab-btn {
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 500;
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  white-space: nowrap;
  transition: all 0.15s;
}
.tab-btn:hover { color: var(--text); }
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }

/* ── Loading ────────────────────────────────── */
.chart-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 60px 0;
  color: var(--text-muted);
  font-size: 14px;
}
.chart-spinner {
  width: 36px; height: 36px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* ── Chart blocks ───────────────────────────── */
.tab-content { display: flex; flex-direction: column; gap: 16px; }

.chart-block {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
}
.chart-block.full  { width: 100%; }
.chart-block.flex-1 { flex: 1; min-width: 0; }
.chart-block.w280  { width: 280px; flex-shrink: 0; }

.chart-header { margin-bottom: 16px; }
.chart-title { font-size: 14px; font-weight: 700; color: var(--text); margin-bottom: 4px; }
.chart-desc  { font-size: 12px; color: var(--text-secondary); }

.chart-area { position: relative; }
.h300 { height: 300px; }
.h280 { height: 280px; }
.h260 { height: 260px; }

/* ── Overview metrics ───────────────────────── */
.metrics-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.metric-tile {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.mt-icon {
  width: 36px; height: 36px;
  border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.mt-icon.indigo { background: var(--accent-subtle); color: var(--accent); }
.mt-icon.emerald { background: var(--accent2-subtle); color: var(--accent2); }
.mt-icon.amber   { background: rgba(245,158,11,0.1); color: #f59e0b; }

.mt-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
.mt-value { font-size: 20px; font-weight: 700; color: var(--text); }

/* ── AI tab ─────────────────────────────────── */
.info-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.info-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
}

.info-card.empty-state {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--text-secondary);
  font-size: 14px;
}

.ic-title { font-size: 14px; font-weight: 700; margin-bottom: 14px; }

.ic-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.ic-stat { display: flex; flex-direction: column; gap: 4px; }
.ic-lbl  { font-size: 11px; color: var(--text-secondary); }
.ic-val  { font-size: 18px; font-weight: 700; color: var(--text); }

.nav-bar-wrap { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.nav-bar-track {
  flex: 1;
  height: 8px;
  background: var(--bg-elevated);
  border-radius: 4px;
  overflow: hidden;
}
.nav-bar-fill {
  height: 100%;
  background: var(--accent2);
  border-radius: 4px;
  transition: width 0.6s ease;
}
.nav-pct { font-size: 16px; font-weight: 700; color: var(--accent2); min-width: 40px; text-align: right; }
.nav-legend { display: flex; gap: 14px; }
.nav-ok   { font-size: 13px; color: var(--accent2); }
.nav-fail { font-size: 13px; color: var(--text-secondary); }

/* ── Homework tab ───────────────────────────── */
.hw-top {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.hw-stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

.hw-stat {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
  text-align: center;
}
.hs-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; }
.hs-val   { font-size: 24px; font-weight: 800; color: var(--text); }
.hs-val.emerald { color: var(--accent2); }
.hs-val.indigo  { color: var(--accent); }
.hs-val.amber   { color: #f59e0b; }

/* ── Students tab ───────────────────────────── */
.students-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.empty-state-box {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 40px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 8px;
  color: var(--text-secondary);
}
.es-icon  { font-size: 32px; margin-bottom: 4px; }
.es-title { font-size: 14px; font-weight: 600; color: var(--text); }
.es-desc  { font-size: 13px; color: var(--text-secondary); max-width: 260px; }

.student-table-wrap {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  overflow-x: auto;
}

.student-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.student-table th {
  text-align: left;
  padding: 8px 12px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border);
}
.student-table td { padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.04); }
.student-table tr:last-child td { border-bottom: none; }
.student-table tr:hover td { background: var(--bg-elevated); }

.td-idx  { color: var(--text-muted); font-weight: 600; width: 40px; }
.td-name { font-weight: 600; color: var(--text); }
.td-date { color: var(--text-secondary); font-family: 'JetBrains Mono', monospace; font-size: 12px; }

.count-bar-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}
.count-bar {
  height: 6px;
  background: var(--accent);
  border-radius: 3px;
  min-width: 4px;
  max-width: 120px;
  opacity: 0.7;
}
.count-bar-wrap span { font-weight: 600; color: var(--text); font-size: 13px; }

/* ── Responsive ─────────────────────────────── */
@media (max-width: 900px) {
  .students-grid  { grid-template-columns: 1fr; }
  .info-cards     { grid-template-columns: 1fr; }
  .metrics-summary-grid { grid-template-columns: 1fr 1fr; }
  .hw-stats-grid  { grid-template-columns: repeat(3, 1fr); }
  .hw-top         { flex-direction: column; }
  .chart-block.w280 { width: 100%; }
}

@media (max-width: 600px) {
  .analytics-page { padding: 20px 16px 60px; }
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
  .hw-stats-grid { grid-template-columns: repeat(2, 1fr); }
  .metrics-summary-grid { grid-template-columns: 1fr; }
}
</style>
