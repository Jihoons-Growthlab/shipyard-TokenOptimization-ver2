import Dashboard from './Dashboard.vue'
import HullList from './HullList.vue'
import PlanGantt from './PlanGantt.vue'
import ProgressInput from './ProgressInput.vue'
import DrawingList from './DrawingList.vue'
import ApprovalInbox from './ApprovalInbox.vue'
import UserMgmt from './UserMgmt.vue'

// 화면 토큰 -> 컴포넌트.
export const screens = {
  dashboard: Dashboard,
  'hull-list': HullList,
  'plan-gantt': PlanGantt,
  progress: ProgressInput,
  'dwg-list': DrawingList,
  'dwg-approval': ApprovalInbox,
  'user-mgmt': UserMgmt,
}
