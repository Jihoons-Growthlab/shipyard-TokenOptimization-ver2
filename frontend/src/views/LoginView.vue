<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client.js'
import scene from '../assets/auth-scene.svg'
import { setToken } from '../stores/session.js'
import { toast } from '../stores/toast.js'

const HEADS = {
  login: ['SWP SHIPYARD', '조선소 통합관리', '호선 · 공정 · 도면 관리 시스템'],
  otp: ['2-STEP VERIFICATION', '구글 2차 인증', 'Google Authenticator 앱에 표시된 6자리 코드를 입력하세요.'],
  signup: ['SIGN UP', '회원가입', '가입 후 관리자 승인이 완료되면 로그인할 수 있습니다.'],
}
const FEATURES = [
  ['호선', '호선별 진척률과 인도 일정을 한눈에'],
  ['공정', '간트 계획부터 일별 실적까지'],
  ['도면', '리비전·결재·배포 이력 관리'],
]
const emptySignup = () => ({
  last_name: '', first_name: '', birth_date: '', phone: '', email: '', emp_no: '', password: '', password_confirm: '',
})

const router = useRouter()
const mode = ref('login')
const error = ref('')
const busy = ref(false)
const creds = reactive({ emp_no: '', password: '' })
const signup = reactive(emptySignup())
const code = ref('')
let otpToken = null

const head = computed(() => HEADS[mode.value])
const vFocus = { mounted: (el) => el.focus() }

function show(next) {
  mode.value = next
  error.value = ''
  code.value = ''
  creds.password = ''
  otpToken = null
}

async function submit(action) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await action()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

function enter(res) {
  setToken(res.access_token)
  router.replace('/')
}

const onLogin = () =>
  submit(async () => {
    const res = await api('/api/auth/login', { method: 'POST', body: { ...creds } })
    if (!res.otp_required) return enter(res)
    show('otp')
    otpToken = res.otp_token
  })

const onOtp = () =>
  submit(async () => {
    enter(await api('/api/auth/otp/verify', { method: 'POST', body: { code: code.value }, token: otpToken }))
  })

const onSignup = () =>
  submit(async () => {
    const res = await api('/api/auth/register', { method: 'POST', body: { ...signup } })
    Object.assign(signup, emptySignup())
    show('login')
    toast.success(res.message)
  })
</script>

<template>
  <div class="auth">
    <img class="auth-scene" :src="scene" alt="" />
    <section class="auth-intro">
      <div class="auth-mark">⚓ SWP SHIPYARD</div>
      <p class="auth-title">설계부터 인도까지,<br />조선소 운영을 한곳에서</p>
      <dl>
        <div v-for="[key, text] in FEATURES" :key="key">
          <dt>{{ key }}</dt>
          <dd>{{ text }}</dd>
        </div>
      </dl>
    </section>

    <section class="auth-card" :class="{ wide: mode === 'signup' }">
      <div class="auth-logo">{{ head[0] }}</div>
      <h1>{{ head[1] }}</h1>
      <p class="auth-sub">{{ head[2] }}</p>

      <form v-if="mode === 'login'" novalidate @submit.prevent="onLogin">
        <div class="auth-fields">
          <label>아이디<input v-model="creds.emp_no" v-focus autocomplete="username" /></label>
          <label>
            비밀번호
            <input v-model="creds.password" type="password" autocomplete="current-password" />
          </label>
        </div>
        <p class="auth-err" role="alert">{{ error }}</p>
        <button class="btn pri auth-submit" :disabled="busy">로그인</button>
        <div class="auth-foot">
          <button type="button" class="auth-link" @click="show('signup')">회원가입</button>
          <span>구글 2차 인증 사용 계정은 다음 단계에서 OTP 입력</span>
        </div>
      </form>

      <form v-else-if="mode === 'otp'" novalidate @submit.prevent="onOtp">
        <div class="auth-fields">
          <label>
            인증 코드
            <input
              v-model="code"
              v-focus
              class="otp-input"
              inputmode="numeric"
              autocomplete="one-time-code"
              maxlength="6"
            />
          </label>
        </div>
        <p class="auth-err" role="alert">{{ error }}</p>
        <button class="btn pri auth-submit" :disabled="busy">확인</button>
        <div class="auth-foot">
          <button type="button" class="auth-link" @click="show('login')">← 로그인으로</button>
        </div>
      </form>

      <form v-else novalidate @submit.prevent="onSignup">
        <div class="auth-fields two">
          <label>성<input v-model="signup.last_name" v-focus maxlength="50" autocomplete="family-name" /></label>
          <label>이름<input v-model="signup.first_name" maxlength="50" autocomplete="given-name" /></label>
          <label>생년월일<input v-model="signup.birth_date" type="date" autocomplete="bday" /></label>
          <label>
            전화번호
            <input v-model="signup.phone" type="tel" placeholder="010-0000-0000" autocomplete="tel" />
          </label>
          <label>이메일<input v-model="signup.email" type="email" autocomplete="email" /></label>
          <label>아이디<input v-model="signup.emp_no" autocomplete="username" /></label>
          <label>비밀번호<input v-model="signup.password" type="password" autocomplete="new-password" /></label>
          <label>
            비밀번호 확인
            <input v-model="signup.password_confirm" type="password" autocomplete="new-password" />
          </label>
        </div>
        <p class="auth-err" role="alert">{{ error }}</p>
        <button class="btn pri auth-submit" :disabled="busy">가입 신청</button>
        <div class="auth-foot">
          <button type="button" class="auth-link" @click="show('login')">← 로그인으로</button>
        </div>
      </form>
    </section>
  </div>
</template>

<style scoped>
.auth {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 48px;
  padding: 40px clamp(28px, 7vw, 120px);
  background: #060f22;
}
.auth-scene {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.auth-intro {
  position: relative;
  z-index: 1;
  width: min(100%, 520px);
  margin-bottom: 22vh;
  color: #fff;
}
.auth-intro::before {
  content: '';
  position: absolute;
  z-index: -1;
  inset: -140px -200px -260px -160px;
  background: radial-gradient(closest-side, rgba(6, 15, 34, 0.8), rgba(6, 15, 34, 0));
}
.auth-mark {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 3px;
  color: #8cc1f2;
}
.auth-title {
  margin: 17px 0 27px;
  font-size: clamp(28px, 3.1vw, 42px);
  font-weight: 700;
  letter-spacing: -0.3px;
  line-height: 1.33;
}
.auth-intro dl {
  margin: 0;
}
.auth-intro dl div {
  display: flex;
  gap: 31px;
  padding: 9px 0;
  font-size: 14px;
  border-top: 1px solid rgba(140, 193, 242, 0.25);
  height: 38px;
  box-sizing: border-box;
}
.auth-intro dt {
  font-weight: 700;
  color: #8cc1f2;
}
.auth-intro dd {
  margin: 0;
  color: #dbe6f3;
}
.auth-card {
  position: relative;
  z-index: 1;
  box-sizing: border-box;
  width: min(100%, 400px);
  padding: 32px 32px 28px;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
}
.auth-card.wide {
  width: min(100%, 560px);
}
.auth-logo {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--pri);
}
.auth-card h1 {
  margin: 6px 0 4px;
  font-size: 22px;
  color: var(--navy);
}
.auth-sub {
  margin: 0 0 18px;
  color: var(--muted);
}
.auth-fields {
  display: grid;
  gap: 10px 12px;
}
.auth-fields.two {
  grid-template-columns: 1fr 1fr;
}
.auth-fields label {
  display: grid;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
}
.auth-fields input {
  box-sizing: border-box;
  width: 100%;
  height: 38px;
  border-radius: 8px;
  padding: 4px 10px;
}
.auth-fields .otp-input {
  height: 46px;
  font-size: 22px;
  text-align: center;
  letter-spacing: 8px;
}
.auth-err {
  min-height: 16px;
  margin: 6px 0 14px;
  font-size: 12px;
  color: var(--err);
}
.auth-submit {
  width: 100%;
  height: 42px;
  font-weight: 700;
}
.auth-foot {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  font-size: 12px;
  color: var(--muted);
}
.auth-link {
  padding: 0;
  border: 0;
  background: none;
  font: inherit;
  color: var(--pri);
  cursor: pointer;
}
@media (max-width: 1000px) {
  .auth {
    grid-template-columns: 1fr;
    justify-items: center;
    padding: 16px;
  }
  .auth::after {
    content: '';
    position: absolute;
    inset: 0;
    background: rgba(6, 15, 34, 0.35);
    pointer-events: none;
  }
  .auth-intro {
    display: none;
  }
}
</style>
