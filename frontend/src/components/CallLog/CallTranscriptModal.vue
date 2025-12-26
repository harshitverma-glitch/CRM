<template>
  <Dialog
    v-model="show"
    :options="{
      title: __('Call Transcript'),
      size: '3xl',
    }"
  >
    <template #body-content>
      <div class="space-y-4">
        <!-- Loading State -->
        <div v-if="isLoading" class="flex flex-col items-center justify-center py-12">
          <LoadingIndicator class="w-8 h-8 text-gray-600 mb-4" />
          <p class="text-gray-600">{{ __('Generating transcript...') }}</p>
          <p class="text-sm text-gray-500 mt-2">{{ __('This may take a moment') }}</p>
        </div>

        <!-- Error State -->
        <div v-else-if="error" class="flex flex-col items-center justify-center py-12">
          <div class="text-red-500 mb-4">
            <svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p class="text-gray-800 font-medium mb-2">{{ __('Failed to load transcript') }}</p>
          <p class="text-sm text-gray-600 mb-4">{{ error }}</p>
          <Button
            variant="solid"
            :label="__('Retry')"
            @click="loadTranscript"
          />
        </div>

        <!-- Transcript Content -->
        <div v-else-if="transcript" class="space-y-4">
          <!-- Cached indicator -->
          <div v-if="isCached" class="flex items-center text-sm text-gray-500">
            <FeatherIcon name="check-circle" class="w-4 h-4 mr-2 text-green-500" />
            <span>{{ __('Loaded from cache') }}</span>
          </div>

          <!-- Transcript text -->
          <div class="bg-gray-50 rounded-lg p-6 max-h-96 overflow-y-auto">
            <div class="prose prose-sm max-w-none">
              <p class="whitespace-pre-wrap text-gray-800 leading-relaxed">{{ transcript }}</p>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex justify-between items-center pt-4 border-t">
            <div class="text-sm text-gray-500">
              {{ transcriptLength }} {{ __('characters') }}
            </div>
            <div class="flex gap-2">
              <Button
                variant="outline"
                :label="copyButtonLabel"
                @click="copyToClipboard"
              >
                <template #prefix>
                  <FeatherIcon :name="copyButtonIcon" class="w-4 h-4" />
                </template>
              </Button>
              <Button
                v-if="!isCached"
                variant="outline"
                :label="__('Refresh')"
                @click="refreshTranscript"
              >
                <template #prefix>
                  <FeatherIcon name="refresh-cw" class="w-4 h-4" />
                </template>
              </Button>
            </div>
          </div>
        </div>

        <!-- No Recording State -->
        <div v-else class="flex flex-col items-center justify-center py-12">
          <div class="text-gray-400 mb-4">
            <svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
          </div>
          <p class="text-gray-600">{{ __('No transcript available') }}</p>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Dialog, Button, FeatherIcon, call, LoadingIndicator, toast } from 'frappe-ui'

const props = defineProps({
  callLogName: {
    type: String,
    required: true
  }
})

const show = defineModel()

const transcript = ref('')
const isLoading = ref(false)
const error = ref(null)
const isCached = ref(false)
const copyButtonLabel = ref(__('Copy'))
const copyButtonIcon = ref('copy')

const transcriptLength = computed(() => {
  return transcript.value ? transcript.value.length : 0
})

// Load transcript when modal opens
watch(show, (newValue) => {
  if (newValue && props.callLogName) {
    loadTranscript()
  }
})

async function loadTranscript() {
  if (!props.callLogName) return

  isLoading.value = true
  error.value = null
  transcript.value = ''

  try {
    const result = await call('crm.api.call_transcription.get_or_create_transcript', {
      call_log_name: props.callLogName
    })

    if (result.success) {
      transcript.value = result.transcript
      isCached.value = result.cached || false
      
      if (!result.cached) {
        toast({
          title: __('Transcript generated successfully'),
          icon: 'check',
          iconClasses: 'text-green-600'
        })
      }
    } else {
      error.value = result.message || __('Failed to load transcript')
    }
  } catch (err) {
    console.error('Transcript load error:', err)
    error.value = err.message || __('An error occurred while loading the transcript')
  } finally {
    isLoading.value = false
  }
}

async function refreshTranscript() {
  if (!props.callLogName) return

  isLoading.value = true
  error.value = null

  try {
    const result = await call('crm.api.call_transcription.refresh_transcript', {
      call_log_name: props.callLogName
    })

    if (result.success) {
      transcript.value = result.transcript
      isCached.value = false
      
      toast({
        title: __('Transcript refreshed successfully'),
        icon: 'check',
        iconClasses: 'text-green-600'
      })
    } else {
      error.value = result.message || __('Failed to refresh transcript')
    }
  } catch (err) {
    console.error('Transcript refresh error:', err)
    error.value = err.message || __('An error occurred while refreshing the transcript')
  } finally {
    isLoading.value = false
  }
}

async function copyToClipboard() {
  if (!transcript.value) return

  try {
    await navigator.clipboard.writeText(transcript.value)
    copyButtonLabel.value = __('Copied!')
    copyButtonIcon.value = 'check'
    
    toast({
      title: __('Transcript copied to clipboard'),
      icon: 'check',
      iconClasses: 'text-green-600'
    })

    // Reset button after 2 seconds
    setTimeout(() => {
      copyButtonLabel.value = __('Copy')
      copyButtonIcon.value = 'copy'
    }, 2000)
  } catch (err) {
    console.error('Copy failed:', err)
    toast({
      title: __('Failed to copy to clipboard'),
      icon: 'x',
      iconClasses: 'text-red-600'
    })
  }
}
</script>

<style scoped>
.prose p {
  margin-bottom: 0;
}
</style>

