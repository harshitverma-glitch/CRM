<template>
  <div v-if="recordingUrl" class="call-recording-player border rounded-lg p-4 bg-surface-gray-1">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-2">
        <FeatherIcon name="mic" class="h-5 w-5 text-ink-gray-7" />
        <span class="text-base font-medium text-ink-gray-9">
          {{ __('Call Recording') }}
        </span>
      </div>
      <Badge v-if="duration" :label="formatDuration(duration)" theme="gray" />
    </div>

    <div v-if="isLoading" class="flex items-center justify-center py-8">
      <LoadingIndicator class="h-6 w-6" />
      <span class="ml-2 text-sm text-ink-gray-6">{{ __('Loading recording...') }}</span>
    </div>

    <div v-else-if="error" class="text-red-600 text-sm">
      <p>{{ error }}</p>
      <Button
        v-if="canRetry"
        :label="__('Try Again')"
        variant="outline"
        size="sm"
        class="mt-2"
        @click="loadRecording"
      />
    </div>

    <div v-else-if="audioUrl" class="space-y-3">
      <!-- Audio Player -->
      <audio
        ref="audioPlayer"
        :src="audioUrl"
        class="hidden"
        @loadedmetadata="onAudioLoaded"
        @timeupdate="onTimeUpdate"
        @ended="onAudioEnded"
        @error="onAudioError"
      />

      <!-- Custom Controls -->
      <div class="flex items-center gap-3">
        <!-- Play/Pause Button -->
        <Button
          :icon="isPlaying ? 'pause' : 'play'"
          variant="solid"
          size="md"
          class="rounded-full"
          @click="togglePlay"
        />

        <!-- Progress Bar -->
        <div class="flex-1">
          <div class="relative h-2 bg-surface-gray-3 rounded-full cursor-pointer" @click="seek">
            <div
              class="absolute h-full bg-blue-500 rounded-full transition-all"
              :style="{ width: progressPercent + '%' }"
            />
            <div
              class="absolute w-4 h-4 bg-blue-600 rounded-full shadow-md transform -translate-y-1/4"
              :style="{ left: progressPercent + '%', marginLeft: '-8px' }"
            />
          </div>
        </div>

        <!-- Time Display -->
        <div class="text-sm text-ink-gray-7 font-mono min-w-[80px]">
          {{ formatTime(currentTime) }} / {{ formatTime(totalDuration) }}
        </div>

        <!-- Volume Control -->
        <Dropdown :options="volumeOptions">
          <template #default>
            <Button
              :icon="volume === 0 ? 'volume-x' : volume < 0.5 ? 'volume-1' : 'volume-2'"
              variant="ghost"
              size="sm"
            />
          </template>
        </Dropdown>

        <!-- Download Button -->
        <Tooltip :text="__('Download Recording')">
          <Button
            icon="download"
            variant="ghost"
            size="sm"
            @click="downloadRecording"
          />
        </Tooltip>
      </div>

      <!-- Waveform Visualization (Optional) -->
      <div v-if="showWaveform" class="h-16 bg-surface-gray-2 rounded flex items-center justify-center">
        <span class="text-xs text-ink-gray-5">{{ __('Waveform visualization') }}</span>
      </div>
    </div>

    <div v-else class="text-center py-4">
      <Button
        :label="__('Load Recording')"
        icon="download-cloud"
        variant="outline"
        @click="loadRecording"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { Button, Dropdown, Badge, Tooltip, LoadingIndicator, call, createResource, FeatherIcon } from 'frappe-ui'

const props = defineProps({
  callLogName: {
    type: String,
    required: true,
  },
  recordingUrl: {
    type: String,
    default: '',
  },
  duration: {
    type: Number,
    default: 0,
  },
  showWaveform: {
    type: Boolean,
    default: false,
  },
})

const audioPlayer = ref(null)
const audioUrl = ref(null)
const isLoading = ref(false)
const error = ref(null)
const canRetry = ref(true)

const isPlaying = ref(false)
const currentTime = ref(0)
const totalDuration = ref(0)
const volume = ref(1)

const progressPercent = computed(() => {
  if (totalDuration.value === 0) return 0
  return (currentTime.value / totalDuration.value) * 100
})

const volumeOptions = computed(() => [
  {
    label: __('Mute'),
    icon: 'volume-x',
    onClick: () => setVolume(0),
  },
  {
    label: __('Low'),
    icon: 'volume-1',
    onClick: () => setVolume(0.3),
  },
  {
    label: __('Medium'),
    icon: 'volume-1',
    onClick: () => setVolume(0.6),
  },
  {
    label: __('High'),
    icon: 'volume-2',
    onClick: () => setVolume(1),
  },
])

async function loadRecording() {
  if (!props.recordingUrl) {
    error.value = __('No recording URL available')
    return
  }

  isLoading.value = true
  error.value = null

  try {
    // Check if recording is already stored in ERPNext
    const localFile = await getLocalRecordingFile()
    
    if (localFile) {
      // Use local file
      console.log('Using existing recording file:', localFile)
      audioUrl.value = localFile
    } else {
      // Download from RingCentral and store
      console.log('Downloading recording from RingCentral...')
      const result = await call('crm.integrations.ringcentral_client.fetch_and_save_recording', {
        call_log_name: props.callLogName,
      })

      if (result.success) {
        console.log('Recording downloaded successfully:', result.file_url)
        audioUrl.value = result.file_url
      } else {
        console.error('Failed to download recording:', result.message)
        error.value = result.message || __('Failed to load recording')
        canRetry.value = true
      }
    }
  } catch (err) {
    console.error('Recording load error:', err)
    error.value = err.message || __('Error loading recording')
    canRetry.value = true
  } finally {
    isLoading.value = false
  }
}

async function getLocalRecordingFile() {
  try {
    const files = await call('frappe.client.get_list', {
      doctype: 'File',
      filters: {
        attached_to_doctype: 'CRM Call Log',
        attached_to_name: props.callLogName,
      },
      fields: ['file_url'],
      limit: 1,
    })

    return files && files.length > 0 ? files[0].file_url : null
  } catch (err) {
    return null
  }
}

function togglePlay() {
  if (!audioPlayer.value) return

  if (isPlaying.value) {
    audioPlayer.value.pause()
    isPlaying.value = false
  } else {
    audioPlayer.value.play()
    isPlaying.value = true
  }
}

function seek(event) {
  if (!audioPlayer.value || totalDuration.value === 0) return

  const rect = event.currentTarget.getBoundingClientRect()
  const x = event.clientX - rect.left
  const percent = x / rect.width
  const time = percent * totalDuration.value

  audioPlayer.value.currentTime = time
}

function setVolume(val) {
  volume.value = val
  if (audioPlayer.value) {
    audioPlayer.value.volume = val
  }
}

function onAudioLoaded() {
  if (audioPlayer.value) {
    totalDuration.value = audioPlayer.value.duration
  }
}

function onTimeUpdate() {
  if (audioPlayer.value) {
    currentTime.value = audioPlayer.value.currentTime
  }
}

function onAudioEnded() {
  isPlaying.value = false
  currentTime.value = 0
  if (audioPlayer.value) {
    audioPlayer.value.currentTime = 0
  }
}

function onAudioError(event) {
  console.error('Audio playback error:', event)
  console.error('Audio element error code:', audioPlayer.value?.error?.code)
  console.error('Audio element error message:', audioPlayer.value?.error?.message)
  console.error('Audio URL was:', audioUrl.value)
  
  const errorMessages = {
    1: 'MEDIA_ERR_ABORTED - The user aborted the audio/video loading',
    2: 'MEDIA_ERR_NETWORK - A network error occurred while loading the audio/video',
    3: 'MEDIA_ERR_DECODE - The audio/video is corrupted or not supported',
    4: 'MEDIA_ERR_SRC_NOT_SUPPORTED - The audio/video format is not supported',
  }
  
  const errorCode = audioPlayer.value?.error?.code
  const errorDetail = errorMessages[errorCode] || 'Unknown audio error'
  
  error.value = __('Failed to load audio file') + ': ' + errorDetail
  isPlaying.value = false
  canRetry.value = true
}

function downloadRecording() {
  if (audioUrl.value) {
    window.open(audioUrl.value, '_blank')
  }
}

function formatTime(seconds) {
  if (!seconds || isNaN(seconds)) return '0:00'
  
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

function formatDuration(seconds) {
  if (!seconds) return '0s'
  
  if (seconds < 60) {
    return `${seconds}s`
  }
  
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  
  if (secs === 0) {
    return `${mins}m`
  }
  
  return `${mins}m ${secs}s`
}

// Keyboard shortcuts
function handleKeyPress(event) {
  if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') return

  switch (event.code) {
    case 'Space':
      event.preventDefault()
      togglePlay()
      break
    case 'ArrowLeft':
      event.preventDefault()
      if (audioPlayer.value) {
        audioPlayer.value.currentTime = Math.max(0, audioPlayer.value.currentTime - 5)
      }
      break
    case 'ArrowRight':
      event.preventDefault()
      if (audioPlayer.value) {
        audioPlayer.value.currentTime = Math.min(
          totalDuration.value,
          audioPlayer.value.currentTime + 5
        )
      }
      break
  }
}

onMounted(() => {
  // Auto-load if local file exists
  if (props.recordingUrl) {
    getLocalRecordingFile().then((localFile) => {
      if (localFile) {
        console.log('Auto-loading existing recording:', localFile)
        audioUrl.value = localFile
      }
    })
  }

  window.addEventListener('keydown', handleKeyPress)
})

onBeforeUnmount(() => {
  if (audioPlayer.value) {
    audioPlayer.value.pause()
  }
  window.removeEventListener('keydown', handleKeyPress)
})

defineExpose({
  loadRecording,
  togglePlay,
})
</script>

<style scoped>
.call-recording-player {
  transition: all 0.2s ease;
}

.call-recording-player:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}
</style>

