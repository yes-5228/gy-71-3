import { request } from './http'

export function fetchContracts(status = '') {
  const query = status ? `?status=${encodeURIComponent(status)}` : ''
  return request(`/contracts${query}`)
}

export function createContract(payload) {
  return request('/contracts', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function updateContract(id, payload) {
  return request(`/contracts/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  })
}

export function terminateContract(id) {
  return request(`/contracts/${id}/terminate`, {
    method: 'POST'
  })
}

export function refundDeposit(id) {
  return request(`/contracts/${id}/refund-deposit`, {
    method: 'POST'
  })
}
