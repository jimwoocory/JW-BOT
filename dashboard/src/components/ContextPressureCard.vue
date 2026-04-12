<template>
  <v-card class="context-pressure-card" elevation="0" border>
    <v-card-title class="pb-3 d-flex align-center justify-space-between">
      <div class="d-flex align-center">
        <v-icon start color="primary">mdi-gauge</v-icon>
        {{ t('title') }}
      </div>
      <v-btn icon size="small" @click="refreshData" :loading="loading">
        <v-icon>mdi-refresh</v-icon>
      </v-btn>
    </v-card-title>

    <v-card-text v-if="loading" class="text-center pa-8">
      <v-progress-circular indeterminate color="primary" />
    </v-card-text>

    <v-card-text v-else-if="error" class="text-center pa-4">
      <v-icon color="error" size="32">mdi-alert-circle</v-icon>
      <p class="mt-2 text-error">{{ error }}</p>
    </v-card-text>

    <v-card-text v-else-if="pressureData">
      <!-- Overall Health Status -->
      <div class="health-status mb-6 text-center">
        <v-chip
          :color="healthColor(pressureData.overall_health)"
          size="large"
          variant="tonal"
          class="health-chip"
        >
          <v-icon start :icon="healthIcon(pressureData.overall_health)" />
          {{ t(`health.${pressureData.overall_health}`) }}
        </v-chip>
        <div class="text-caption text-medium-emphasis mt-1">
          Last updated: {{ formatTime(pressureData.timestamp) }}
        </div>
      </div>

      <!-- Pressure Distribution -->
      <div class="section mb-6">
        <div class="section-title">{{ t('distribution.title') }}</div>
        <v-row dense>
          <v-col cols="4">
            <div class="pressure-stat text-center pa-3 rounded bg-red-lighten-5">
              <div class="text-h5 font-weight-bold text-red-darken-1">
                {{ pressureData.pressure_distribution?.high || 0 }}
              </div>
              <div class="text-caption">{{ t('distribution.high') }}</div>
            </div>
          </v-col>
          <v-col cols="4">
            <div class="pressure-stat text-center pa-3 rounded bg-orange-lighten-5">
              <div class="text-h5 font-weight-bold text-orange-darken-1">
                {{ pressureData.pressure_distribution?.medium || 0 }}
              </div>
              <div class="text-caption">{{ t('distribution.medium') }}</div>
            </div>
          </v-col>
          <v-col cols="4">
            <div class="pressure-stat text-center pa-3 rounded bg-green-lighten-5">
              <div class="text-h5 font-weight-bold text-green-darken-1">
                {{ pressureData.pressure_distribution?.low || 0 }}
              </div>
              <div class="text-caption">{{ t('distribution.low') }}</div>
            </div>
          </v-col>
        </v-row>
      </div>

      <!-- Key Metrics -->
      <v-row dense class="mb-4">
        <v-col cols="12" sm="6">
          <div class="metric-item d-flex align-center pa-3 rounded bg-grey-lighten-4">
            <v-icon color="info" class="mr-3">mdi-account-group-outline</v-icon>
            <div>
              <div class="text-caption text-medium-emphasis">{{ t('metrics.totalSessions') }}</div>
              <div class="text-h6 font-weight-bold">{{ pressureData.total_sessions || 0 }}</div>
            </div>
          </div>
        </v-col>
        <v-col cols="12" sm="6">
          <div class="metric-item d-flex align-center pa-3 rounded bg-grey-lighten-4">
            <v-icon color="warning" class="mr-3">mdi-alert-outline</v-icon>
            <div>
              <div class="text-caption text-medium-emphasis">{{ t('metrics.nearLimit') }}</div>
              <div class="text-h6 font-weight-bold">{{ pressureData.sessions_near_limit || 0 }}</div>
            </div>
          </div>
        </v-col>
      </v-row>

      <!-- Token Usage -->
      <div class="section">
        <div class="section-title">{{ t('tokens.title') }}</div>
        <div class="d-flex align-center mb-2">
          <span class="text-body-2 mr-2">{{ t('tokens.totalUsed') }}:</span>
          <strong>{{ formatNumber(pressureData.total_tokens_used) }}</strong>
          <span class="text-caption text-medium-emphasis ml-2">tokens</span>
        </div>
        <div class="d-flex align-center">
          <span class="text-body-2 mr-2">{{ t('tokens.avgPerSession') }}:</span>
          <strong>{{ formatNumber(pressureData.avg_tokens_per_session) }}</strong>
          <span class="text-caption text-medium-emphasis ml-2">tokens</span>
        </div>
      </div>

      <!-- Alerts Preview (if any) -->
      <div v-if="alerts && alerts.length > 0" class="section mt-4">
        <div class="section-title d-flex align-center">
          <v-icon size="16" color="warning" class="mr-1">mdi-bell-ring</v-icon>
          {{ t('alerts.title') }} ({{ alerts.length }})
        </div>
        <v-list density="compact" class="bg-transparent">
          <v-list-item
            v-for="(alert, index) in alerts.slice(0, 3)"
            :key="index"
            :class="{ 'mb-1': index < Math.min(alerts.length, 3) - 1 }"
          >
            <template v-slot:prepend>
              <v-icon
                :color="alert.severity === 'critical' ? 'error' : alert.severity === 'warning' ? 'warning' : 'info'"
                size="20"
              >
                {{ alert.severity === 'critical' ? 'mdi-alert-circle' : alert.severity === 'warning' ? 'mdi-alert' : 'mdi-information' }}
              </v-icon>
            </template>
            <v-list-item-title class="text-wrap">{{ alert.message }}</v-list-item-title>
            <v-list-item-subtitle class="text-wrap">{{ alert.recommended_action }}</v-list-item-subtitle>
          </v-list-item>
        </v-list>
        <v-btn
          v-if="alerts.length > 3"
          variant="text"
          size="small"
          color="primary"
          block
          @click="$router.push('/context-monitor')"
        >
          View All Alerts
        </v-btn>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useI18n } from '@/i18n/composables'

const props = defineProps({
  autoRefresh: {
    type: Boolean,
    default: false,
  },
  refreshInterval: {
    type: Number,
    default: 30000,
  },
})

const { t } = useI18n()

const loading = ref(false)
const error = ref(null)
const pressureData = ref(null)
const alerts = ref([])

let refreshTimer = null

const loadData = async () => {
  loading.value = true
  error.value = null

  try {
    const [pressureRes, alertsRes] = await Promise.all([
      fetch('/api/context/pressure'),
      fetch('/api/context/alerts'),
    ])

    const pressureResult = await pressureRes.json()
    const alertsResult = await alertsRes.json()

    if (pressureResult.success) {
      pressureData.value = pressureResult.data
    }

    if (alertsResult.success) {
      alerts.value = alertsResult.data.alerts
    }
  } catch (err) {
    console.error('Failed to load context data:', err)
    error.value = 'Failed to load context monitoring data'
  } finally {
    loading.value = false
  }
}

const refreshData = async () => {
  await loadData()
}

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

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString()
}

const formatNumber = (num) => {
  if (num == null) return '0'
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
  return num.toString()
}

onMounted(() => {
  loadData()

  if (props.autoRefresh) {
    refreshTimer = setInterval(loadData, props.refreshInterval)
  }
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped lang="scss">
.context-pressure-card {
  .health-chip {
    font-size: 1rem;
    font-weight: 600;
    padding: 0.75rem 1.5rem;
  }

  .section {
    margin-bottom: 1rem;

    .section-title {
      font-size: 0.9rem;
      font-weight: 600;
      margin-bottom: 0.75rem;
      color: rgba(0, 0, 0, 0.87);
    }
  }

  .metric-item {
    transition: background-color 0.2s;

    &:hover {
      background-color: #e0e0e0;
    }
  }

  .pressure-stat {
    border: 1px solid currentColor;
    opacity: 0.9;

    &:hover {
      opacity: 1;
    }
  }
}
</style>
