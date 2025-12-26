<template>
  <div v-show="showCallPopup" v-bind="$attrs">
    <div
      ref="callPopup"
      class="fixed z-20 flex w-60 cursor-move select-none flex-col rounded-lg bg-surface-gray-7 p-4 text-ink-gray-2 shadow-2xl"
      :style="style"
    >
      <div class="flex flex-row-reverse items-center gap-1">
        <MinimizeIcon
          class="h-4 w-4 cursor-pointer"
          @click="closeCallWindow"
        />
      </div>
      <div class="flex flex-col items-center justify-center gap-3">
        <Avatar
          v-if="contact?.image"
          :image="contact.image"
          :label="contact.full_name"
          class="relative flex !h-24 !w-24 items-center justify-center [&>div]:text-[30px]"
        />
        <div class="flex flex-col items-center justify-center gap-1">
          <div class="text-xl font-medium">
            {{ contact?.full_name ?? __('Unknown') }}
          </div>
          <div class="text-sm text-ink-gray-5">{{ contact?.mobile_no }}</div>
        </div>
        <div class="my-1 text-base">
          {{ __('Opening RingCentral...') }}
        </div>
        <div class="flex gap-2">
          <Button
            size="md"
            variant="solid"
            theme="green"
            :label="__('Call')"
            class="rounded-lg"
            @click="makeRingCentralCall"
          >
            <template #prefix>
              <PhoneIcon class="h-4 w-4 fill-white" />
            </template>
          </Button>
          <Button
            size="md"
            variant="outline"
            :label="__('Cancel')"
            @click="closeCallWindow"
            class="rounded-lg"
          >
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import PhoneIcon from '@/components/Icons/PhoneIcon.vue'
import MinimizeIcon from '@/components/Icons/MinimizeIcon.vue'
import { Avatar, call, toast } from 'frappe-ui'
import { ref, computed } from 'vue'
import { useDraggable } from '@vueuse/core'

const callPopup = ref()
const showCallPopup = ref(false)
const contact = ref({})
const mobileNumber = ref('')

const { x, y } = useDraggable(callPopup, {
  initialValue: { x: 10, y: window.innerHeight - 350 },
})

const style = computed(() => {
  return {
    top: y.value + 'px',
    left: x.value + 'px',
  }
})

function setup() {
  // RingCentral doesn't need special setup like Twilio SDK
  console.log('RingCentral call button ready')
}

async function makeOutgoingCall(number) {
  if (!number) {
    toast.error(__('No phone number provided'))
    return
  }

  mobileNumber.value = number
  
  // Try to fetch contact details
  try {
    const response = await call('crm.api.get_contact_by_phone', {
      number: number,
    })
    if (response) {
      contact.value = response
    } else {
      contact.value = {
        full_name: __('Unknown'),
        mobile_no: number,
      }
    }
  } catch (error) {
    contact.value = {
      full_name: __('Unknown'),
      mobile_no: number,
    }
  }

  showCallPopup.value = true
  
  // Auto-trigger call after a short delay
  setTimeout(() => {
    makeRingCentralCall()
  }, 500)
}

function makeRingCentralCall() {
  if (!mobileNumber.value) {
    toast.error(__('No phone number provided'))
    return
  }

  // Create a CRM Call Log
  createCallLog(mobileNumber.value)

  // Try RingCentral app first (rcapp:// protocol)
  // If app not installed, fallback to web interface
  const appUrl = `rcapp://r/call?number=${encodeURIComponent(mobileNumber.value)}`
  const webUrl = `https://app.ringcentral.com/app/dialer?number=${encodeURIComponent(mobileNumber.value)}`
  
  // Attempt to open app
  const iframe = document.createElement('iframe')
  iframe.style.display = 'none'
  iframe.src = appUrl
  document.body.appendChild(iframe)
  
  // Fallback to web after short delay if app doesn't open
  setTimeout(() => {
    window.open(webUrl, '_blank')
    document.body.removeChild(iframe)
  }, 1000)

  toast.success(__('Opening RingCentral to call {0}', [mobileNumber.value]))
  
  // Close popup after initiating call
  setTimeout(() => {
    closeCallWindow()
  }, 1500)
}

async function createCallLog(number) {
  try {
    await call('crm.integrations.ringcentral_api.create_manual_call_log', {
      phone_number: number,
      contact_name: contact.value.full_name || 'Unknown',
    })
  } catch (error) {
    console.error('Error creating call log:', error)
    // Don't show error to user - call should still proceed
  }
}

function closeCallWindow() {
  showCallPopup.value = false
  contact.value = {}
  mobileNumber.value = ''
}

defineExpose({
  setup,
  makeOutgoingCall,
})
</script>

<style scoped>
/* Pulse animation for avatar */
@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
</style>

