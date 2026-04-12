<template>
  <div class="hall-page" :class="{ 'is-dark': isDark }">
    <v-container fluid class="hall-shell pa-4 pa-md-6">
      <!-- Header -->
      <div class="hall-header mb-6">
        <div>
          <div class="eyebrow">{{ t('header.eyebrow') }}</div>
          <h1 class="hall-title">{{ t('header.title') }}</h1>
          <p class="hall-subtitle">{{ t('header.subtitle') }}</p>
        </div>
        <div class="header-actions">
          <v-btn color="primary" variant="flat" rounded="pill" @click="createDiscussion" :loading="creating">
            <v-icon start>mdi-plus</v-icon>
            {{ t('actions.newDiscussion') }}
          </v-btn>
        </div>
      </div>

      <!-- Overview Cards -->
      <v-row class="mb-6">
        <v-col cols="12" md="3" sm="6">
          <v-card class="overview-card" elevation="0" border>
            <v-card-text class="pa-4">
              <div class="d-flex align-center justify-space-between">
                <div>
                  <div class="text-caption text-medium-emphasis">{{ t('overview.totalAgents') }}</div>
                  <div class="text-h4 font-weight-bold mt-1">{{ overview.total_agents || 0 }}</div>
                </div>
                <v-icon size="32" color="primary">mdi-account-group</v-icon>
              </div>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" md="3" sm="6">
          <v-card class="overview-card" elevation="0" border>
            <v-card-text class="pa-4">
              <div class="d-flex align-center justify-space-between">
                <div>
                  <div class="text-caption text-medium-emphasis">{{ t('overview.activeDiscussions') }}</div>
                  <div class="text-h4 font-weight-bold mt-1">{{ overview.total_discussions || 0 }}</div>
                </div>
                <v-icon size="32" color="success">mdi-forum</v-icon>
              </div>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" md="3" sm="6">
          <v-card class="overview-card" elevation="0" border>
            <v-card-text class="pa-4">
              <div class="d-flex align-center justify-space-between">
                <div>
                  <div class="text-caption text-medium-emphasis">{{ t('overview.activeTasks') }}</div>
                  <div class="text-h4 font-weight-bold mt-1">{{ overview.active_tasks || 0 }}</div>
                </div>
                <v-icon size="32" color="warning">mdi-clipboard-list</v-icon>
              </div>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" md="3" sm="6">
          <v-card class="overview-card" elevation="0" border>
            <v-card-text class="pa-4">
              <div class="d-flex align-center justify-space-between">
                <div>
                  <div class="text-caption text-medium-emphasis">{{ t('overview.pendingApprovals') }}</div>
                  <div class="text-h4 font-weight-bold mt-1">{{ overview.pending_approvals || 0 }}</div>
                </div>
                <v-icon size="32" color="error">mdi-alert-circle</v-icon>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Main Content Grid -->
      <v-row>
        <!-- Agent Roster Panel -->
        <v-col cols="12" md="3">
          <v-card class="roster-panel" elevation="0" border height="100%">
            <v-card-title class="pb-2">
              <v-icon start>mdi-account-multiple</v-icon>
              {{ t('roster.title') }}
            </v-card-title>
            <v-card-text class="pa-0">
              <v-list density="compact">
                <v-list-item v-for="agent in agents" :key="agent.id" :value="agent.id">
                  <template v-slot:prepend>
                    <v-avatar size="32" :color="getRoleColor(agent.role)" class="mr-2">
                      <span class="text-white text-caption font-weight-bold">
                        {{ agent.display_name.charAt(0).toUpperCase() }}
                      </span>
                    </v-avatar>
                  </template>
                  <v-list-item-title>{{ agent.display_name }}</v-list-item-title>
                  <v-list-item-subtitle>
                    <v-chip size="x-small" :color="getStatusColor(agent.status)" variant="tonal">
                      {{ agent.status }}
                    </v-chip>
                    <span class="ml-2 text-caption">{{ getRoleLabel(agent.role) }}</span>
                  </v-list-item-subtitle>
                  <template v-slot:append>
                    <v-icon size="16" color="grey">mdi-dots-vertical</v-icon>
                  </template>
                </v-list-item>
              </v-list>
            </v-card-text>
          </v-card>
        </v-col>

        <!-- Discussions Panel -->
        <v-col cols="12" md="9">
          <v-card class="discussions-panel" elevation="0" border height="100%">
            <v-card-title class="pb-2 d-flex align-center justify-space-between">
              <div>
                <v-icon start>mdi-forum-outline</v-icon>
                {{ t('discussions.title') }}
              </div>
              <v-btn icon size="small" @click="loadDiscussions" :loading="loadingDiscussions">
                <v-icon>mdi-refresh</v-icon>
              </v-btn>
            </v-card-title>

            <v-card-text class="pa-0">
              <v-tabs v-model="activeTab" color="primary">
                <v-tab value="active">{{ t('tabs.active') }}</v-tab>
                <v-tab value="tasks">{{ t('tabs.tasks') }} ({{ pendingTasks.length }})</v-tab>
                <v-tab value="approvals">{{ t('tabs.approvals') }} ({{ approvals.length }})</v-tab>
              </v-tabs>

              <v-window v-model="activeTab">
                <!-- Active Discussions Tab -->
                <v-window-item value="active">
                  <div v-if="loadingDiscussions" class="text-center pa-8">
                    <v-progress-circular indeterminate color="primary" />
                  </div>
                  <div v-else-if="discussions.length === 0" class="text-center pa-8 text-medium-emphasis">
                    <v-icon size="48" color="grey-lighten-1">mdi-forum-outline</v-icon>
                    <p class="mt-2">{{ t('discussions.empty') }}</p>
                  </div>
                  <v-list v-else lines="two">
                    <v-list-item
                      v-for="discussion in discussions"
                      :key="discussion.id"
                      @click="selectDiscussion(discussion)"
                      :class="{ 'bg-grey-lighten-4': selectedDiscussion?.id === discussion.id }"
                    >
                      <template v-slot:prepend>
                        <v-icon :color="discussion.has_pending_tasks ? 'warning' : 'success'">
                          {{ discussion.has_pending_tasks ? 'mdi-alert-circle' : 'mdi-check-circle' }}
                        </v-icon>
                      </template>
                      <v-list-item-title>
                        Discussion #{{ discussion.id.slice(0, 8) }}
                        <v-chip v-if="discussion.has_pending_tasks" size="x-small" color="warning" class="ml-2">
                          Pending Tasks
                        </v-chip>
                      </v-list-item-title>
                      <v-list-item-subtitle>
                        {{ discussion.message_count }} messages · Last activity: {{ formatTime(discussion.last_activity) }}
                      </v-list-item-subtitle>
                      <template v-slot:append>
                        <v-icon>mdi-chevron-right</v-icon>
                      </template>
                    </v-list-item>
                  </v-list>
                </v-window-item>

                <!-- Pending Tasks Tab -->
                <v-window-item value="tasks">
                  <div v-if="pendingTasks.length === 0" class="text-center pa-8 text-medium-emphasis">
                    <v-icon size="48" color="grey-lighten-1">mdi-clipboard-check</v-icon>
                    <p class="mt-2">{{ t('tasks.empty') }}</p>
                  </div>
                  <v-list v-else lines="two">
                    <v-list-item v-for="task in pendingTasks" :key="task.id">
                      <template v-slot:prepend>
                        <v-icon :color="getPriorityColor(task.priority)">
                          mdi-clipboard-text
                        </v-icon>
                      </template>
                      <v-list-item-title>{{ task.content?.slice(0, 80) || 'Untitled Task' }}</v-list-item-title>
                      <v-list-item-subtitle>
                        <v-chip size="x-small" :color="getStatusColor(task.status)" variant="tonal">
                          {{ task.status }}
                        </v-chip>
                        <span class="ml-2">Assigned to: {{ task.assignee || 'Unassigned' }}</span>
                      </v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-window-item>

                <!-- Approvals Tab -->
                <v-window-item value="approvals">
                  <div v-if="approvals.length === 0" class="text-center pa-8 text-medium-emphasis">
                    <v-icon size="48" color="grey-lighten-1">mdi-check-decagram</v-icon>
                    <p class="mt-2">{{ t('approvals.empty') }}</p>
                  </div>
                  <v-list v-else lines="two">
                    <v-list-item v-for="approval in approvals" :key="approval.id">
                      <template v-slot:prepend>
                        <v-icon color="error">mdi-alert-octagon</v-icon>
                      </template>
                      <v-list-item-title>{{ approval.content?.slice(0, 80) || 'Pending Review' }}</v-list-item-title>
                      <v-list-item-subtitle>
                        Status: {{ approval.status }}
                      </v-list-item-subtitle>
                      <template v-slot:append>
                        <v-btn size="small" color="success" variant="tonal">Approve</v-btn>
                        <v-btn size="small" color="error" variant="tonal" class="ml-2">Reject</v-btn>
                      </template>
                    </v-list-item>
                  </v-list>
                </v-window-item>
              </v-window>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Discussion Detail Dialog -->
      <v-dialog v-model="showDetailDialog" max-width="900" scrollable>
        <v-card v-if="selectedDiscussionDetail">
          <v-card-title class="d-flex align-center justify-space-between">
            <span>Discussion #{{ selectedDiscussionDetail.id?.slice(0, 8) }}</span>
            <v-btn icon @click="showDetailDialog = false"><v-icon>mdi-close</v-icon></v-btn>
          </v-card-title>

          <v-divider />

          <v-card-text class="pa-4" style="max-height: 60vh; overflow-y: auto;">
            <v-timeline align="start" side="end" density="compact" truncate-line="both">
              <v-timeline-item
                v-for="message in selectedDiscussionDetail.messages"
                :key="message.id"
                :dot-color="getMessageTypeColor(message.type)"
                :icon="getMessageTypeIcon(message.type)"
                fill-dot
                size="small"
              >
                <div class="pl-2">
                  <div class="d-flex align-center mb-1">
                    <strong>{{ message.author }}</strong>
                    <v-chip size="x-small" :color="getTypeChipColor(message.type)" class="ml-2">
                      {{ message.type }}
                    </v-chip>
                    <span class="ml-auto text-caption text-medium-emphasis">
                      {{ formatTime(message.timestamp) }}
                    </span>
                  </div>
                  <div class="text-body-2">{{ message.content }}</div>
                  <div v-if="message.type === 'task'" class="mt-2">
                    <v-chip size="small" :color="getPriorityColor(message.priority)" variant="tonal">
                      Priority: {{ message.priority }}
                    </v-chip>
                    <v-chip v-if="message.assignee" size="small" color="info" variant="tonal" class="ml-2">
                      Assigned to: {{ message.assignee }}
                    </v-chip>
                  </div>
                </div>
              </v-timeline-item>
            </v-timeline>
          </v-card-text>

          <v-divider />

          <v-card-actions class="pa-4">
            <v-textarea
              v-model="newMessage"
              label="Type a message..."
              rows="2"
              auto-grow
              variant="outlined"
              hide-details
            ></v-textarea>
            <v-btn color="primary" @click="postMessage" :loading="postingMessage" class="ml-2">
              Send
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </v-container>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useI18n } from '@/i18n/composables'
import { useTheme } from 'vuetify'

const { t, tm } = useI18n()
const theme = useTheme()
const isDark = computed(() => theme.global.current.value.dark)

// Helper function for authenticated fetch
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

const loading = ref(false)
const creating = ref(false)
const loadingDiscussions = ref(false)
const postingMessage = ref(false)

const overview = ref({})
const agents = ref([])
const discussions = ref([])
const pendingTasks = ref([])
const approvals = ref([])

const activeTab = ref('active')
const selectedDiscussion = ref(null)
const selectedDiscussionDetail = ref(null)
const showDetailDialog = ref(false)
const newMessage = ref('')

const loadOverview = async () => {
  try {
    const data = await authFetch('/api/hall/overview')
    if (data.status === 'ok') {
      overview.value = data.data
    }
  } catch (error) {
    console.error('Failed to load overview:', error)
  }
}

const loadAgents = async () => {
  try {
    const data = await authFetch('/api/hall/agents')
    if (data.status === 'ok') {
      agents.value = data.data.agents
    }
  } catch (error) {
    console.error('Failed to load agents:', error)
  }
}

const loadDiscussions = async () => {
  loadingDiscussions.value = true
  try {
    const [discRes, tasksRes, apprRes] = await Promise.all([
      authFetch('/api/hall/discussions'),
      authFetch('/api/hall/tasks/pending'),
      authFetch('/api/hall/tasks/approvals'),
    ])

    const discData = discRes
    const tasksData = tasksRes
    const apprData = apprRes

    if (discData.success) discussions.value = discData.data.discussions
    if (tasksData.success) pendingTasks.value = tasksData.data.tasks
    if (apprData.success) approvals.value = apprData.data.approvals
  } catch (error) {
    console.error('Failed to load discussions:', error)
  } finally {
    loadingDiscussions.value = false
  }
}

const createDiscussion = async () => {
  creating.value = true
  try {
    const data = await authFetch('/api/hall/discussion', {
      method: 'POST',
      body: JSON.stringify({
        title: `Discussion ${new Date().toLocaleString()}`,
        author: 'operator',
        message: '',
      }),
    })
    
    if (data.status === 'ok') {
      await loadDiscussions()
      await loadOverview()
    }
  } catch (error) {
    console.error('Failed to create discussion:', error)
  } finally {
    creating.value = false
  }
}

const selectDiscussion = async (discussion) => {
  selectedDiscussion.value = discussion
  showDetailDialog.value = true

  try {
    const data = await authFetch(`/api/hall/discussion/${discussion.id}`)
    if (data.status === 'ok') {
      selectedDiscussionDetail.value = data.data
    }
  } catch (error) {
    console.error('Failed to load discussion detail:', error)
  }
}

const postMessage = async () => {
  if (!newMessage.value.trim() || !selectedDiscussionDetail.value) return

  postingMessage.value = true
  try {
    const data = await authFetch(
      `/api/hall/discussion/${selectedDiscussionDetail.value.id}/message`,
      {
        method: 'POST',
        body: JSON.stringify({
          type: 'message',
          author: 'operator',
          content: newMessage.value,
        }),
      },
    )
    
    if (data.status === 'ok') {
      newMessage.value = ''
      await selectDiscussion(selectedDiscussion.value)
    }
  } catch (error) {
    console.error('Failed to post message:', error)
  } finally {
    postingMessage.value = false
  }
}

const getRoleColor = (role) => {
  const colors = {
    coordinator: 'primary',
    archivist: 'info',
    analyst: 'success',
    contributor: 'secondary',
  }
  return colors[role] || 'grey'
}

const getStatusColor = (status) => {
  const colors = {
    active: 'success',
    idle: 'warning',
    offline: 'error',
    pending: 'info',
    assigned: 'info',
    in_progress: 'primary',
    pending_review: 'warning',
    blocked: 'error',
  }
  return colors[status] || 'grey'
}

const getPriorityColor = (priority) => {
  const colors = {
    critical: 'error',
    high: 'warning',
    medium: 'info',
    low: 'success',
  }
  return colors[priority] || 'grey'
}

const getMessageTypeColor = (type) => {
  const colors = {
    system: 'grey',
    message: 'primary',
    task: 'warning',
    handoff: 'info',
  }
  return colors[type] || 'grey'
}

const getMessageTypeIcon = (type) => {
  const icons = {
    system: 'mdi-information',
    message: 'mdi-message-text',
    task: 'mdi-clipboard-text',
    handoff: 'mdi-swap-horizontal',
  }
  return icons[type] || 'mdi-circle'
}

const getTypeChipColor = (type) => {
  const colors = {
    system: 'grey',
    message: 'primary',
    task: 'warning',
    handoff: 'info',
  }
  return colors[type] || 'grey'
}

const getRoleLabel = (role) => {
  const labels = {
    coordinator: 'Coordinator',
    archivist: 'Archivist',
    analyst: 'Analyst',
    contributor: 'Contributor',
  }
  return labels[role] || role
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString()
}

onMounted(async () => {
  await Promise.all([loadOverview(), loadAgents(), loadDiscussions()])
})
</script>

<style scoped lang="scss">
.hall-page {
  min-height: 100vh;
  background: #f5f5f5;

  &.is-dark {
    background: #121212;
  }

  .hall-header {
    .eyebrow {
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: rgb(var(--v-theme-primary));
    }

    .hall-title {
      font-size: 2rem;
      font-weight: 700;
      margin: 0.25rem 0;
    }

    .hall-subtitle {
      font-size: 1rem;
      color: rgba(0, 0, 0, 0.6);
      margin: 0;
    }
  }

  .overview-card {
    transition: transform 0.2s;

    &:hover {
      transform: translateY(-2px);
    }
  }

  .roster-panel,
  .discussions-panel {
    overflow: hidden;
  }
}
</style>
