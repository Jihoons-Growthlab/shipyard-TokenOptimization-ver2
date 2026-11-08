<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api/client.js'
import PageHeader from '../components/PageHeader.vue'
import { loadSession, session } from '../stores/session.js'
import { toast } from '../stores/toast.js'

defineProps({ token: { type: String, required: true } })

const STATUS = { pending: ['승인대기', 'warn'], approved: ['승인', 'ok'], rejected: ['반려', 'bad'], disabled: ['중지', ''] }
const filter = reactive({ status: '', q: '' })
const data = ref({ users: [], total: 0, pending: 0 })
const groups = ref([])
const mode = ref('') // '' 미선택, 'new', 'edit'
const selected = ref(null)
const form = reactive({})
const busy = ref(false)

const isSelf = computed(() => selected.value?.emp_no === session.me?.emp_no)
const title = computed(() =>
  mode.value === 'edit' ? `회원 수정 — ${selected.value.display_name}` : mode.value === 'new' ? '회원 등록' : '입력 / 수정',
)

function fill(u) {
  Object.assign(form, {
    last_name: u?.last_name ?? '',
    first_name: u?.first_name ?? '',
    birth_date: u?.birth_date ?? '',
    phone: u?.phone ?? '',
    email: u?.email ?? '',
    emp_no: u?.emp_no ?? '',
    password: '',
    status: u?.status ?? 'approved',
    group: u?.groups[0]?.code ?? '',
    totp_enabled: u?.totp_enabled ?? false,
  })
}

async function run(action) {
  busy.value = true
  try {
    await action()
  } catch (e) {
    toast.error(e.message)
  } finally {
    busy.value = false
  }
}

async function load() {
  data.value = await api('/api/users', { params: { status: filter.status, q: filter.q } })
  if (selected.value) selected.value = data.value.users.find((u) => u.emp_no === selected.value.emp_no) ?? selected.value
}

const search = () => run(load)
const reset = () => {
  Object.assign(filter, { status: '', q: '' })
  search()
}

function select(u) {
  selected.value = u
  mode.value = 'edit'
  fill(u)
}

function startNew() {
  selected.value = null
  mode.value = 'new'
  fill(null)
}

const save = () =>
  run(async () => {
    const { group, ...rest } = form
    const body = { ...rest, groups: group ? [group] : [] }
    const editing = mode.value === 'edit'
    const user = editing
      ? await api(`/api/users/${encodeURIComponent(selected.value.emp_no)}`, { method: 'PATCH', body })
      : await api('/api/users', { method: 'POST', body })
    toast.success('저장되었습니다.')
    select(user)
    await load()
    if (user.emp_no === session.me?.emp_no) await loadSession()
  })

const remove = () => {
  if (isSelf.value) return toast.error('로그인 중인 본인 계정은 삭제할 수 없습니다.')
  if (!confirm(`회원 ${selected.value.emp_no} 을(를) 삭제합니다.`)) return
  run(async () => {
    await api(`/api/users/${encodeURIComponent(selected.value.emp_no)}`, { method: 'DELETE' })
    toast.success('삭제되었습니다.')
    selected.value = null
    mode.value = ''
    await load()
  })
}

const approve = () =>
  run(async () => {
    const user = await api(`/api/users/${encodeURIComponent(selected.value.emp_no)}/approve`, {
      method: 'POST',
      body: { groups: form.group ? [form.group] : [] },
    })
    toast.success(`${user.display_name} 님의 가입을 승인했습니다.`)
    select(user)
    await load()
  })

onMounted(() =>
  run(async () => {
    groups.value = await api('/api/auth-groups')
    await load()
  }),
)
</script>

<template>
  <div class="screen">
    <PageHeader :token="token" desc="상단 목록 / 하단 입력·수정 (CRUD)" />
    <div class="half">
      <div class="bar">
        <select v-model="filter.status" aria-label="상태">
          <option value="">상태 전체</option>
          <option v-for="(s, k) in STATUS" :key="k" :value="k">{{ s[0] }}</option>
        </select>
        <input v-model="filter.q" placeholder="아이디/이름/이메일/전화" aria-label="검색어" @keyup.enter="search" />
        <button type="button" class="btn pri" :disabled="busy" @click="search">조회</button>
        <button type="button" class="btn" :disabled="busy" @click="reset">초기화</button>
        <span class="count muted">{{ data.total }}명 · 승인대기 {{ data.pending }}명</span>
      </div>
      <div class="tw grow">
        <table class="table">
          <thead>
            <tr>
              <th>아이디</th><th>이름</th><th>이메일</th><th>전화번호</th><th>생년월일</th>
              <th>상태</th><th>2차인증</th><th>권한그룹</th><th>가입일</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="u in data.users"
              :key="u.emp_no"
              :class="{ sel: u.emp_no === selected?.emp_no }"
              @click="select(u)"
            >
              <td class="id">{{ u.emp_no }}</td>
              <td>{{ u.display_name }}</td>
              <td>{{ u.email }}</td>
              <td>{{ u.phone }}</td>
              <td>{{ u.birth_date }}</td>
              <td><span class="badge" :class="STATUS[u.status]?.[1]">{{ STATUS[u.status]?.[0] ?? u.status }}</span></td>
              <td>{{ u.totp_enabled ? '사용' : '-' }}</td>
              <td>{{ u.groups.map((g) => g.name).join(', ') || '-' }}</td>
              <td>{{ u.created_at }}</td>
            </tr>
            <tr v-if="!data.users.length"><td colspan="9" class="muted">조회된 회원이 없습니다.</td></tr>
          </tbody>
        </table>
      </div>
    </div>
    <section class="half card">
      <h3>{{ title }}</h3>
      <template v-if="mode">
        <form class="form c4" novalidate @submit.prevent="save">
          <label class="field">성 *<input v-model="form.last_name" maxlength="50" /></label>
          <label class="field">이름 *<input v-model="form.first_name" maxlength="50" /></label>
          <label class="field">생년월일 *<input v-model="form.birth_date" type="date" /></label>
          <label class="field">전화번호 *<input v-model="form.phone" placeholder="010-0000-0000" /></label>
          <label class="field s2">이메일 *<input v-model="form.email" type="email" /></label>
          <label class="field">아이디 *<input v-model="form.emp_no" :readonly="mode === 'edit'" /></label>
          <label class="field">{{ mode === 'edit' ? '비밀번호 (변경 시만 입력)' : '비밀번호 *' }}
            <input v-model="form.password" type="password" placeholder="8자 이상" autocomplete="new-password" />
          </label>
          <label class="field">상태
            <select v-model="form.status">
              <option v-for="(s, k) in STATUS" :key="k" :value="k">{{ s[0] }}</option>
            </select>
          </label>
          <label class="field">권한 그룹
            <select v-model="form.group">
              <option value="">없음</option>
              <option v-for="g in groups" :key="g.code" :value="g.code">{{ g.name }}</option>
            </select>
          </label>
          <div class="field">구글 2차인증
            <label class="chk"><input v-model="form.totp_enabled" type="checkbox" /> 사용 (등록된 사용자만)</label>
          </div>
          <label class="field">가입일<input :value="selected?.created_at ?? '-'" readonly /></label>
        </form>
      </template>
      <p v-else class="muted">목록에서 회원을 선택하거나 [신규]를 누르세요.</p>
      <div class="actions">
        <button type="button" class="btn" :disabled="busy" @click="startNew">신규</button>
        <button type="button" class="btn pri" :disabled="busy || !mode" @click="save">저장</button>
        <button type="button" class="btn danger" :disabled="busy || mode !== 'edit' || isSelf" @click="remove">삭제</button>
        <button v-if="mode === 'edit' && selected.status === 'pending'" type="button" class="btn ok" :disabled="busy" @click="approve">
          가입 승인
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.screen {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.half {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}
.half.card {
  margin: 10px 0 0;
  overflow: auto;
}
.bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.bar select {
  width: 110px;
}
.count {
  margin-left: auto;
}
.grow {
  flex: 1;
  min-height: 0;
}
.id {
  font-weight: 600;
}
.s2 {
  grid-column: span 2;
}
.chk {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 30px;
  color: var(--ink);
}
</style>
