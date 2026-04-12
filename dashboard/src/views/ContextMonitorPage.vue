<template>
  <div class="context-monitor-page" :class="{ 'is-dark': isDark }">
    <v-container fluid class="monitor-shell pa-4 pa-md-6">
      <!-- Header -->
      <div class="monitor-header mb-6">
        <div>
          <div class="eyebrow">{{ t('header.eyebrow') }}</div>
          <h1 class="monitor-title">{{ t('header.title') }}</h1>
          <p class="monitor-subtitle">{{ t('header.subtitle') }}</p>
        </div>
        <div class="header-actions">
          <v-switch
            v-model="autoRefresh"
            color="primary"
            hide-details
            density="compact"
            :label="t('actions.autoRefresh')"
            class="mr-4"
          />
          <v-btn color="primary" variant="flat" rounded="pill" @click="refreshAll" :loading="loading">
            <v-icon start>mdi-refresh</v-icon>
            {{ t('actions.refresh') }}
          </v-btn>
        </div>
      </div>

      <!-- Summary Cards Row -->
      <v-row class="mb-6">
        <v-col cols="12" md="3" sm="6">
          <v-card class="summary-card" elevation="0" border>
            <v-card-text class="pa-4">
              <div class="d-flex align-center justify-space-between">
                <div>
                  <div class="text-caption text-medium-emphasis">{{ t('summary.totalSessions') }}</div>
                  <div class="text-h4 font-weight-bold mt-1">{{ summary.overview?.total_sessions || 0 }}</div>
                </div>
                <v-icon size="32" color="primary">mdi-account-group-outline</v-icon>
              </div>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" md="3" sm="6">
          <v-card class="summary-card" elevation="0" border>
            <v-card-text class="pa-4">
              <div class="d-flex align-center justify-space-between">
                <div>
                  <div class="text-caption text-medium-emphasis">{{ t('summary.nearLimit') }}</div>
                  <div class="text-h4 font-weight-bold mt-1 text-warning">
                    {{ summary.overview?.sessions_near_limit || 0 }}
                  </div>
                </div>
                <v-icon size="32" color="warning">mdi-alert-outline</v-icon>
              </div>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" md="3" sm="6">
          <v-card class="summary-card" elevation="0" border>
            <v-card-text class="pa-4">
              <div class="d-flex align-center justify-space-between">
                <div>
                  <div class="text-caption text-medium-emphasis">{{ t('summary.totalTokens') }}</div>
                  <div class="text-h4 font-weight-bold mt-1">{{ formatNumber(summary.overview?.total_tokens_used) }}</div>
                </div>
                <v-icon size="32" color="info">mdi-counter</v-icon>
              </div>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" md="3" sm="6">
          <v-card class="summary-card" elevation="0" border>
            <v-card-text class="pa-4">
              <div class="d-flex align-center justify-space-between">
                <div>
                  <div class="text-caption text-medium-emphasis">{{ t('summary.alerts') }}</div>
                  <div class="text-h4 font-weight-bold mt-1 text-error">
                    {{ summary.alert_summary?.total || 0 }}
                  </div>
                </div>
                <v-icon size="32" color="error">mdi-bell-ring</v-icon>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Main Content Grid -->
      <v-row>
        <!-- Pressure Distribution Chart -->
        <v-col cols="12" md="8">
          <v-card class="pressure-chart-card" elevation="0" border>
            <v-card-title class="pb-2">
              <v-icon start>mdi-chart-pie</v-icon>
              {{ t('charts.pressureDistribution') }}
            </v-card-title>
            <v-card-text>
              <apexchart
                type="donut"
                height="350"
                :options="pressureChartOptions"
                :series="pressureChartSeries"
              />
            </v-card-text>
          </v-card>
        </v-col>

        <!-- Health Status & Alerts -->
        <v-col cols="12" md="4">
          <v-card class="health-status-card" elevation="0" border height="100%">
            <v-card-title class="pb-2">
              <v-icon start>mdi-heart-pulse</v-icon>
              {{ t('health.title') }}
            </v-card-title>
            <v-card-text>
              <!-- Overall Health Badge -->
              <div class="text-center mb-6">
                <v-chip
                  :color="healthColor(summary.overview?.overall_health)"
                  size="x-large"
                  variant="tonal"
                  class="health-badge"
                >
                  <v-icon
                    start
                    :icon="healthIcon(summary.overview?.overall_health)"
                    size="24"
                  />
                  {{ t(`health.${summary.overview?.overall_health || 'unknown'}`) }}
                </v-chip>
              </div>

              <!-- Alert Count Breakdown -->
              <div class="alert-breakdown">
                <div class="d-flex justify-space-between align-center mb-2">
                  <span class="text-body-2">{{ t('alerts.critical') }}:</span>
                  <v-chip size="small" color="error" variant="tonal">
                    {{ summary.alert_summary?.critical || 0 }}
                  </v-chip>
                </div>
                <div class="d-flex justify-space-between align-center mb-2">
                  <span class="text-body-2">{{ t('alerts.warning') }}:</span>
                  <v-chip size="small" color="warning" variant="tonal">
                    {{ summary.alert_summary?.warning || 0 }}
                  </v-chip>
                </div>
                <div class="d-flex justify-space-between align-center">
                  <span class="text-body-2">{{ t('alerts.info') }}:</span>
                  <v-chip size="small" color="info" variant="tonal">
                    {{ summary.alert_summary?.info || 0 }}
                  </v-chip>
                </div>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Sessions Table -->
      <v-row class="mt-6">
        <v-col cols="12">
          <v-card class="sessions-table-card" elevation="0" border>
            <v-card-title class="pb-2 d-flex align-center justify-space-between">
              <div>
                <v-icon start>mdi-table-large</v-icon>
                {{ t('sessions.title') }}
              </div>
              <v-text-field
                v-model="searchQuery"
                :label="t('sessions.search')"
                prepend-inner-icon="mdi-magnify"
                variant="outlined"
                hide-details
                density="compact"
                style="max-width: 300px;"
              ></v-text-field>
            </v-card-title>

            <v-card-text>
              <v-data-table
                :headers="sessionHeaders"
                :items="filteredSessions"
                :loading="loadingSessions"
                :items-per-page="15"
                class="elevation-0"
              >
                <template v-slot:item.context_usage_percent="{ value }">
                  <v-progress-linear
                    :model-value="value"
                    :color="getPressureColor(value)"
                    height="20"
                    rounded
                    class="my-2"
                  >
                    <strong>{{ value }}%</strong>
                  </v-progress-linear>
                </template>

                <template v-slot:item.status="{ value }">
                  <v-chip :color="getStatusColor(value)" size="small" variant="tonal">
                    {{ value }}
                  </v-chip>
                </template>

                <template v-slot:item.actions="{ item }">
                  <v-btn icon size="small" variant="text" @click="viewSessionDetail(item)">
                    <v-icon>mdi-eye</v-icon>
                  </v-btn>
                </template>
              </v-data-table>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Recommendations Panel -->
      <v-row class="mt-6" v-if="recommendations.length > 0">
        <v-col cols="12">
          <v-card class="recommendations-card" elevation="0" border>
            <v-card-title class="pb-2">
              <v-icon start color="info">mdi-lightbulb-on</v-icon>
              {{ t('recommendations.title') }}
            </v-card-title>
            <v-card-text>
              <v-list lines="two">
                <v-list-item
                  v-for="(rec, index) in recommendations"
                  :key="index"
                  :prepend-avatar="'💡'"
                >
                  <v-list-item-title>{{ rec }}</v-list-item-title>
                </v-list-item>
              </v-list>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Session Detail Dialog -->
      <v-dialog v-model="showDetailDialog" max-width="800" scrollable>
        <v-card v-if="selectedSession">
          <v-card-title class="d-flex align-center justify-space-between">
            <span>{{ t('detail.title') }} - {{ selectedSession.id }}</span>
            <v-btn icon @click="showDetailDialog = false"><v-icon>mdi-close</v-icon></v-btn>
          </v-card-title>

          <v-divider />

          <v-card-text class="pa-4">
            <v-row dense>
              <v-col cols="12" sm="6">
                <div class="detail-item">
                  <strong>Platform:</strong> {{ selectedSession.platform }}
                </div>
              </v-col>
              <v-col cols="12" sm="6">
                <div class="detail-item">
                  <strong>User ID:</strong> {{ selectedSession.user_id }}
                </div>
              </v-col>
              <v-col cols="12" sm="6">
                <div class="detail-item">
                  <strong>Status:</strong>
                  <v-chip :color="getStatusColor(selectedSession.status)" size="small" variant="tonal">
                    {{ selectedSession.status }}
                  </v-chip>
                </div>
              </v-col>
              <v-col cols="12" sm="6">
                <div class="detail-item">
                  <strong>Last Activity:</strong> {{ formatTime(selectedSession.last_activity) }}
                </div>
              </v-col>
            </v-row>

            <v-divider class="my-4"></v-divider>

            <h3 class="mb-3">{{ t('detail.pressureHistory') }}</h3>
            <apexchart
              type="line"
              height="250"
              :options="historyChartOptions"
              :series="historyChartSeries"
            />

            <v-divider class="my-4"></v-divider>

            <h3 class="mb-3">{{ t('detail.recommendations') }}</h3>
            <v-list>
              <v-list-item v-for="(rec, index) in sessionRecommendations" :key="index">
                <v-list-item-title>{{ rec }}</v-list-item-title>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-dialog>
    </v-container>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from '@/i18n/composables'
import { useTheme } from 'vuetify'

const { t } = useI18n()
const theme = useTheme()
const isDark = computed(() => theme.global.current.value.dark)

const loading = ref(false)
const loadingSessions = ref(false)
const autoRefresh = ref(false)
const searchQuery = ref('')
const showDetailDialog = ref(false)

const summary = ref({})
const sessions = ref([])
const recommendations = ref([])
const selectedSession = ref(null)
const sessionRecommendations = ref([])

let refreshTimer = null

const authFetch = async (url, options = {}) => {
  const token = localStorage.getItem('token')
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers
  }
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  
  const response = await fetch(url, {
    ...options,
    headers
  })
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Request failed' }))
    throw new Error(error.message || `HTTP ${response.status}`)
  }
  
  return response.json()
}

const refreshAll = async () => {
  await Promise.all([loadSummary(), loadSessions()])
}

const loadSummary = async () => {
  try {
    const data = await authFetch('/api/context/summary')
    if (data.status === 'ok') {
      summary.value = data.data
      recommendations.value = data.data.recommendations || []
    }
  } catch (error) {
    console.error('Failed to load summary:', error)
  }
}

const loadSessions = async () => {
  loadingSessions.value = true
  try {
    const data = await authFetch('/api/context/sessions?limit=100')
    if (data.status === 'ok') {
      sessions.value = data.data.sessions || []
    }
  } catch (error) {
    console.error('Failed to load sessions:', error)
  } finally {
    loadingSessions.value = false
  }
}

const viewSessionDetail = async (session) => {
  selectedSession.value = session

  try {
    const data = await authFetch(`/api/context/session/${session.id}`)
    if (data.status === 'ok') {
      sessionRecommendations.value = data.data.recommendations || []
    }
  } catch (error) {
    console.error('Failed to load session detail:', error)
  }

  showDetailDialog.value = true
}

const filteredSessions = computed(() => {
  if (!searchQuery.value) return sessions.value

  const query = searchQuery.value.toLowerCase()
  return sessions.value.filter(
    (s) =>
      s.id.toLowerCase().includes(query) ||
      s.platform.toLowerCase().includes(query) ||
      s.user_id.toLowerCase().includes(query),
  )
})

const sessionHeaders = [
  { title: 'Session ID', key: 'id', width: '200px' },
  { title: 'Platform', key: 'platform', width: '120px' },
  { title: 'User ID', key: 'user_id' },
  { title: 'Messages', key: 'message_count', width: '100px' },
  { title: 'Context Usage', key: 'context_usage_percent', sortable: true },
  { title: 'Status', key: 'status', width: '120px' },
  { title: 'Actions', key: 'actions', sortable: false, width: '80px' },
]

const pressureChartOptions = computed(() => ({
  chart: {
    type: 'donut',
  },
  labels: ['High Pressure (>80%)', 'Medium (50-80%)', 'Low (<50%)'],
  colors: ['#ef4444', '#f97316', '#22c55e'],
  legend: {
    position: 'bottom',
  },
  plotOptions: {
    pie: {
      donut: {
        labels: {
          show: true,
          name: {
            show: true,
          },
          value: {
            show: true,
          },
        },
      },
    },
  },
}))

const pressureChartSeries = computed(() => [
  summary.value.overview?.pressure_distribution?.high || 0,
  summary.value.overview?.pressure_distribution?.medium || 0,
  summary.value.overview?.pressure_distribution?.low || 0,
])

const historyChartOptions = computed(() => ({
  chart: {
    type: 'line',
    zoom: {
      enabled: false,
    },
  },
  xaxis: {
    type: 'datetime',
  },
  yaxis: {
    title: {
      text: 'Pressure %',
    },
    min: 0,
    max: 100,
  },
  colors: ['#3b82f6'],
  stroke: {
    curve: 'smooth',
  },
}))

const historyChartSeries = computed(() => {
  if (!selectedSession.value?.pressure_history) return []

  return [
    {
      name: 'Context Pressure',
      data: selectedSession.value.pressure_history.map((h) => ({
        x: new Date(h.timestamp).getTime(),
        y: h.pressure_percent,
      })),
    },
  ]
})

const healthColor = (health) => {
  const colors = {
    healthy: 'success',
    warning: 'warning',
    degraded: 'error',
  }
  return colors[health] || 'grey'
}

const healthIcon = (health) => {
  const icons = {
    healthy: 'mdi-check-circle',
    warning: 'mdi-alert-circle',
    degraded: 'mdi-close-circle',
  }
  return icons[health] || 'mdi-help-circle'
}

const getPressureColor = (value) => {
  if (value >= 90) return 'error'
  if (value >= 70) return 'warning'
  if (value >= 50) return 'info'
  return 'success'
}

const getStatusColor = (status) => {
  const colors = {
    active: 'success',
    idle: 'warning',
    offline: 'error',
  }
  return colors[status] || 'grey'
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleString()
}

const formatNumber = (num) => {
  if (num == null) return '0'
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
  return num.toString()
}

onMounted(async () => {
  await refreshAll()

  if (autoRefresh.value) {
    refreshTimer = setInterval(refreshAll, 30000)
  }
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped lang="scss">
.context-monitor-page {
  min-height: 100vh;
  background: #f5f5f5;

  &.is-dark {
    background: #121212;
  }

  .monitor-header {
    .eyebrow {
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: rgb(var(--v-theme-primary));
    }

    .monitor-title {
      font-size: 2rem;
      font-weight: 700;
      margin: 0.25rem 0;
    }

    .monitor-subtitle {
      font-size: 1rem;
      color: rgba(0, 0, 0, 0.6);
      margin: 0;
    }
  }

  .summary-card {
    transition: transform 0.2s;

    &:hover {
      transform: translateY(-2px);
    }
  }

  .health-badge {
    font-size: 1.1rem;
    padding: 1rem 2rem;
  }

  .detail-item {
    padding: 0.5rem 0;
  }
}
</style>
