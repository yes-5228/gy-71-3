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
            <th>操作与提示</th>
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
            <td class="action-col-wrap">
              <template v-if="contract.status === 'active'">
                <div v-if="!contract.can_terminate" class="block-reason">
                  <span class="block-reason-title">
                    <strong>无法终止：</strong>{{ contract.terminate_reason }}
                  </span>
                  <div class="block-actions">
                    <span class="todo-label">待处理：</span>
                    <button
                      v-if="contract.deposit > 0 && contract.deposit_status !== 'refunded'"
                      type="button"
                      class="small-button"
                      title="先退还押金再终止合同"
                      @click="requestRefundDeposit(contract)"
                    >
                      ① 退还押金
                    </button>
                    <span
                      v-if="hasUnpaidBillsHint(contract)"
                      class="hint-chip warning"
                    >
                      ② 请前往账单管理结清未支付账单
                    </span>
                  </div>
                </div>
                <div v-else class="ok-reason">
                  <span class="ok-chip">可正常终止</span>
                </div>
                <div class="action-row">
                  <button
                    type="button"
                    class="small-button"
                    title="编辑合同信息"
                    @click="openEdit(contract)"
                  >
                    编辑
                  </button>
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
                </div>
              </template>
              <div v-else class="action-row">
                <button
                  type="button"
                  class="small-button"
                  title="编辑合同信息"
                  @click="openEdit(contract)"
                >
                  查看/编辑
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 编辑合同弹窗 -->
    <div v-if="editing" class="modal-mask" @click.self="closeEdit">
      <div class="modal-card">
        <div class="modal-header">
          <h3>编辑合同</h3>
          <button type="button" class="ghost-button" @click="closeEdit">×</button>
        </div>
        <div class="modal-body">
          <div class="info-line">
            <span class="info-label">合同号：</span>
            <span>{{ editing.contract_no }}</span>
          </div>
          <div class="info-line">
            <span class="info-label">工位：</span>
            <span>{{ editing.workstation?.code || '-' }}</span>
          </div>
          <div class="info-line">
            <span class="info-label">押金：</span>
            <span>{{ currency(editing.deposit) }} · <StatusBadge :value="depositStatusLabel(editing.deposit_status)" /></span>
            <span class="muted-note">（押金状态仅能通过「退还押金」操作变更）</span>
          </div>
          <div class="form-grid modal-form">
            <label>
              <span>租户名称</span>
              <input v-model="editForm.tenant_name" placeholder="租户名称" required />
            </label>
            <label>
              <span>联系人/电话</span>
              <input v-model="editForm.tenant_contact" placeholder="联系人/电话" />
            </label>
            <label>
              <span>结束日期</span>
              <input v-model="editForm.end_date" type="date" />
            </label>
            <label>
              <span>合同状态</span>
              <select v-model="editForm.status">
                <option value="active">履行中</option>
                <option value="expired">已到期</option>
                <option value="terminated">已终止</option>
              </select>
            </label>
          </div>
          <div v-if="editStatusBlocked" class="warn-box">
            <strong>提示：</strong>{{ editStatusBlocked }}<br />
            如需将状态改为「{{ statusText(editForm.status) }}」，请先处理完所有前置事项再保存。
          </div>
          <p v-if="editError" class="error">{{ editError }}</p>
        </div>
        <div class="modal-footer">
          <button type="button" class="ghost-button" @click="closeEdit">取消</button>
          <button type="button" class="small-button" @click="submitEdit">保存修改</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { createContract, fetchContracts, refundDeposit, terminateContract, updateContract } from '../api/contracts'
import { fetchWorkstations } from '../api/workstations'
import SectionToolbar from '../components/SectionToolbar.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { currency, statusText, todayISO } from '../utils/formatters'

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

// 编辑相关
const editing = ref(null)
const editForm = reactive({
  tenant_name: '',
  tenant_contact: '',
  end_date: '',
  status: ''
})
const editError = ref('')

const editStatusBlocked = computed(() => {
  if (!editing.value) return ''
  const newStatus = editForm.status
  const current = editing.value.status
  if (newStatus === current) return ''
  if (newStatus !== 'terminated' && newStatus !== 'expired') return ''
  if (!editing.value.can_terminate) {
    return editing.value.terminate_reason || '存在待处理事项，暂不可变更为结束状态'
  }
  return ''
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

function hasUnpaidBillsHint(contract) {
  const reason = contract.terminate_reason || ''
  return reason.includes('未结清账单') || reason.includes('账单')
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
    if (editing.value && editing.value.id === contract.id) {
      openEdit(contracts.value.find((c) => c.id === contract.id) || editing.value)
    }
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

// 编辑合同
function openEdit(contract) {
  editing.value = contract
  editForm.tenant_name = contract.tenant_name
  editForm.tenant_contact = contract.tenant_contact
  editForm.end_date = contract.end_date
  editForm.status = contract.status
  editError.value = ''
}

function closeEdit() {
  editing.value = null
  editError.value = ''
}

async function submitEdit() {
  editError.value = ''
  clearMessages()
  if (!editing.value) return

  if (editStatusBlocked.value) {
    editError.value = editStatusBlocked.value
    return
  }

  try {
    const payload = {
      tenant_name: editForm.tenant_name,
      tenant_contact: editForm.tenant_contact,
      end_date: editForm.end_date,
      status: editForm.status
    }
    await updateContract(editing.value.id, payload)
    success.value = `合同 ${editing.value.contract_no} 修改成功`
    closeEdit()
    await load()
  } catch (err) {
    editError.value = err.message
  }
}

onMounted(load)
</script>
