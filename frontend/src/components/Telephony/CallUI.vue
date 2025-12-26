<template>
  <TwilioCallUI ref="twilio" />
  <ExotelCallUI ref="exotel" />
  <RingCentralCallUI ref="ringcentral" />
  <Dialog
    v-model="show"
    :options="{
      title: __('Make call'),
      actions: [
        {
          label: __('Call using {0}', [callMedium]),
          variant: 'solid',
          onClick: makeCallUsing,
        },
      ],
    }"
  >
    <template #body-content>
      <div class="flex flex-col gap-4">
        <FormControl
          type="text"
          v-model="mobileNumber"
          :label="__('Mobile Number')"
        />
        <FormControl
          type="select"
          v-model="callMedium"
          :label="__('Calling Medium')"
          :options="callMediumOptions"
        />
        <div class="flex flex-col gap-1">
          <FormControl
            type="checkbox"
            v-model="isDefaultMedium"
            :label="__('Make {0} as default calling medium', [callMedium])"
          />

          <div v-if="isDefaultMedium" class="text-sm text-ink-gray-4">
            {{
              __('You can change the default calling medium from the settings')
            }}
          </div>
        </div>
      </div>
    </template>
  </Dialog>
</template>
<script setup>
import TwilioCallUI from '@/components/Telephony/TwilioCallUI.vue'
import ExotelCallUI from '@/components/Telephony/ExotelCallUI.vue'
import RingCentralCallUI from '@/components/Telephony/RingCentralCallUI.vue'
import {
  twilioEnabled,
  exotelEnabled,
  ringcentralEnabled,
  defaultCallingMedium,
} from '@/composables/settings'
import { globalStore } from '@/stores/global'
import { FormControl, call, toast } from 'frappe-ui'
import { nextTick, ref, watch, computed } from 'vue'

const { setMakeCall } = globalStore()

const twilio = ref(null)
const exotel = ref(null)
const ringcentral = ref(null)

const callMedium = ref('RingCentral')
const isDefaultMedium = ref(false)

const callMediumOptions = computed(() => {
  const options = []
  if (twilioEnabled.value) options.push('Twilio')
  if (exotelEnabled.value) options.push('Exotel')
  if (ringcentralEnabled.value) options.push('RingCentral')
  return options.length > 0 ? options : ['RingCentral']
})

const show = ref(false)
const mobileNumber = ref('')

function makeCall(number) {
  // Count enabled calling mediums
  const enabledMediums = [
    twilioEnabled.value,
    exotelEnabled.value,
    ringcentralEnabled.value,
  ].filter(Boolean).length

  // If multiple mediums are enabled and no default is set, show dialog
  if (enabledMediums > 1 && !defaultCallingMedium.value) {
    mobileNumber.value = number
    show.value = true
    return
  }

  // Set call medium based on what's enabled or default
  if (defaultCallingMedium.value) {
    callMedium.value = defaultCallingMedium.value
  } else if (ringcentralEnabled.value) {
    callMedium.value = 'RingCentral'
  } else if (twilioEnabled.value) {
    callMedium.value = 'Twilio'
  } else if (exotelEnabled.value) {
    callMedium.value = 'Exotel'
  }

  mobileNumber.value = number
  makeCallUsing()
}

function makeCallUsing() {
  if (isDefaultMedium.value && callMedium.value) {
    setDefaultCallingMedium()
  }

  if (callMedium.value === 'Twilio') {
    twilio.value.makeOutgoingCall(mobileNumber.value)
  }

  if (callMedium.value === 'Exotel') {
    exotel.value.makeOutgoingCall(mobileNumber.value)
  }

  if (callMedium.value === 'RingCentral') {
    ringcentral.value.makeOutgoingCall(mobileNumber.value)
  }

  show.value = false
}

async function setDefaultCallingMedium() {
  await call('crm.integrations.api.set_default_calling_medium', {
    medium: callMedium.value,
  })

  defaultCallingMedium.value = callMedium.value
  toast.success(
    __('Default calling medium set successfully to {0}', [callMedium.value]),
  )
}

watch(
  [twilioEnabled, exotelEnabled, ringcentralEnabled],
  ([twilioValue, exotelValue, ringcentralValue]) =>
    nextTick(() => {
      if (ringcentralValue) {
        ringcentral.value.setup()
        callMedium.value = 'RingCentral'
      }

      if (twilioValue) {
        twilio.value.setup()
        if (!ringcentralValue) callMedium.value = 'Twilio'
      }

      if (exotelValue) {
        exotel.value.setup()
        if (!ringcentralValue && !twilioValue) callMedium.value = 'Exotel'
      }

      if (twilioValue || exotelValue || ringcentralValue) {
        setMakeCall(makeCall)
      }
    }),
  { immediate: true },
)
</script>
