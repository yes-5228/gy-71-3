<template>
  <section class="panel">
    <SectionToolbar eyebrow="Contracts" title="租赁合同签订">
      <select v-model="statusFilter" @change="loadContracts">
        <option value="">全部合同</option>
        <option value="active">履行中</option>
        <option value="terminated">已终止</option>
        <option value="expired">已到期</option>
      </select>
    </SectionToolbar>

    <form class="form-grid" @submit.prevent="submit">
      <input v-model="form.tenant_name" placeholder="租户名称" required />
      <input v-model="form.tenant_contact" placeholder="联系人/电话" />
      <select v-model.number="form.workstation_id" required>
        <option value="" disabled>选择可租工位</option>
        <option v-for="item in availableWorkstations" :key="item.id" :value="item.id">
          {{ item.code }} / {{ item.area }} / {{ currency(item.monthly_rent) }}
        </option>
      </select>
      <input v-model="form.start_date" type="date" required />
      <input v-model="form.end_date" type="date" required />
      <input v-model.number="form.monthly_rent" type="number" min="0" placeholder="月租金" required />
      <input v-model.number="form.deposit" type="number" min="0" placeholder="押金" />
      <button type="submit">签订合同</button>
    </form>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="success" class="success">{{ success }}</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>合同号</th>
            <th>租户</th>
            <th>工位</th>
            <th>租期</th>
            <th>月租金</th>
            <th>押金</th>
            <th>押金状态</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="contract in contracts" :key="contract.id">
            <td>{{ contract.contract_no }}</td>
            <td>{{ contract.tenant_name }}<small>{{ contract.tenant_contact }}</small></td>
            <td>{{ contract.workstation?.code || '-' }}</td>
            <td>{{ contract.start_date }} 至 {{ contract.end_date }}</td>
            <td>{{ currency(contract.monthly_rent) }}</td>
            <td>{{ currency(contract.deposit) }}</td>
            <td><StatusBadge :value="depositStatusLabel(contract.deposit_status)" /></td>
            <td><StatusBadge :value="contract.status" /></td>
            <td class="action-col">
              <template v-if="contract.status === 'active'">
                <button
                  v-if="contract.deposit > 0 && contract.deposit_status !== 'refunded'"
                  type="button"
                  class="small-button"
                  title="确认退还押金"
                  @click="requestRefundDeposit(contract)"
                >
                  退还押金
                </button>
                <button
                  type="button"
                  class="small-button danger"
                  :disabled="!contract.can_terminate"
                  :title="contract.can_terminate ? '确认终止该合同' : contract.terminate_reason"
                  @click="requestTerminate(contract)"
                >
                  终止合同
                </button>
              </template>
              <span v-else>-</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { createContract, fetchContracts, refundDeposit, terminateContract } from '../api/contracts'
import { fetchWorkstations } from '../api/workstations'
import SectionToolbar from '../components/SectionToolbar.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { currency, todayISO } from '../utils/formatters'

const contracts = ref([])
const availableWorkstations = ref([])
const statusFilter = ref('')
const error = ref('')
const success = ref('')
const form = reactive({
  tenant_name: '',
  tenant_contact: '',
  workstation_id: '',
  start_date: todayISO(),
  end_date: '',
  monthly_rent: 0,
  deposit: 0
})

watch(
  () => form.workstation_id,
  (id) => {
    const item = availableWorkstations.value.find((workstation) => workstation.id === Number(id))
    if (item) {
      form.monthly_rent = Number(item.monthly_rent)
      form.deposit = Number(item.monthly_rent) * 2
    }
  }
)

function depositStatusLabel(status) {
  const map = {
    unhandled: '未处理',
    refunded: '已退还'
  }
  return map[status] || status || '已退还'
}

function clearMessages() {
  error.value = ''
  success.value = ''
}

async function loadContracts() {
  clearMessages()
  try {
    contracts.value = await fetchContracts(statusFilter.value)
  } catch (err) {
    error.value = err.message
  }
}

async function loadWorkstations() {
  availableWorkstations.value = await fetchWorkstations('available')
}

async function load() {
  try {
    await Promise.all([loadContracts(), loadWorkstations()])
  } catch (err) {
    error.value = err.message
  }
}

async function submit() {
  clearMessages()
  try {
    await createContract({ ...form, workstation_id: Number(form.workstation_id) })
    Object.assign(form, {
      tenant_name: '',
      tenant_contact: '',
      workstation_id: '',
      start_date: todayISO(),
      end_date: '',
      monthly_rent: 0,
      deposit: 0
    })
    success.value = '合同签订成功'
    await load()
  } catch (err) {
    error.value = err.message
  }
}

async function requestRefundDeposit(contract) {
  clearMessages()
  const confirmed = window.confirm(
    `确认退还 ${contract.contract_no}（${contract.tenant_name}）的押金 ${currency(contract.deposit)}？`
  )
  if (!confirmed) return
  try {
    await refundDeposit(contract.id)
    success.value = `合同 ${contract.contract_no} 的押金已成功退还`
    await load()
  } catch (err) {
    error.value = err.message
  }
}

async function requestTerminate(contract) {
  clearMessages()
  if (!contract.can_terminate) {
    error.value = contract.terminate_reason || '当前合同无法终止'
    return
  }
  const confirmed = window.confirm(
    `确认终止合同 ${contract.contract_no}（${contract.tenant_name}）？终止后工位将恢复可租赁状态，该操作不可撤销。`
  )
  if (!confirmed) return
  try {
    await terminateContract(contract.id)
    success.value = `合同 ${contract.contract_no} 已成功终止`
    await load()
  } catch (err) {
    error.value = err.message
  }
}

onMounted(load)
</script>
