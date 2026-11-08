import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import WeatherWidget from '../components/WeatherWidget.vue'

const sample = (region, source = 'SAMPLE') => ({ region, source, tempC: 17.6, condition: '맑음', humidity: 52, windMs: 3.2 })
const json = (body) => new Response(JSON.stringify(body), { status: 200 })
const regionOf = (call) => new URL(call[0], 'http://x').searchParams.get('region')

describe('날씨 위젯', () => {
  let wrapper
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn(async (url) => json(sample(new URL(url, 'http://x').searchParams.get('region')))))
  })
  afterEach(() => wrapper?.unmount())

  it('WEATHER-T01 기본 울산, 지역별 요청과 저장', async () => {
    wrapper = mount(WeatherWidget)
    expect(wrapper.text()).toContain('날씨 조회 중…')
    await flushPromises()
    expect(regionOf(fetch.mock.calls[0])).toBe('울산')
    expect(wrapper.text()).toContain('17.6℃')
    expect(wrapper.text()).toContain('습도 52% · 바람 3.2m/s')
    expect(wrapper.text()).toContain('샘플')
    await wrapper.find('select').setValue('거제')
    await flushPromises()
    expect(regionOf(fetch.mock.calls[1])).toBe('거제')
    expect(localStorage.getItem('swp_region')).toBe('거제')
  })

  it('저장된 지역을 쓰고, 잘못된 값은 기본값으로 둔다', async () => {
    localStorage.setItem('swp_region', '목포')
    wrapper = mount(WeatherWidget)
    await flushPromises()
    expect(regionOf(fetch.mock.calls[0])).toBe('목포')
    wrapper.unmount()
    localStorage.setItem('swp_region', '부산')
    wrapper = mount(WeatherWidget)
    await flushPromises()
    expect(regionOf(fetch.mock.calls[1])).toBe('울산')
  })

  it('WEATHER-T02 샘플을 LIVE로 표시하지 않고, LIVE는 LIVE로 표시한다', async () => {
    wrapper = mount(WeatherWidget)
    await flushPromises()
    expect(wrapper.text()).not.toContain('LIVE')
    fetch.mockImplementation(async () => json(sample('거제', 'LIVE')))
    await wrapper.find('select').setValue('거제')
    await flushPromises()
    expect(wrapper.find('.wbadge').text()).toBe('LIVE')
  })

  it('요청 실패 문구', async () => {
    fetch.mockRejectedValue(new TypeError('x'))
    wrapper = mount(WeatherWidget)
    await flushPromises()
    expect(wrapper.text()).toContain('날씨 조회 실패')
  })

  it('WEATHER-T03 지역 변경 뒤 늦은 응답을 버린다', async () => {
    const pending = {}
    fetch.mockImplementation((url) => new Promise((r) => (pending[new URL(url, 'http://x').searchParams.get('region')] = r)))
    wrapper = mount(WeatherWidget)
    await wrapper.find('select').setValue('목포')
    pending['목포'](json({ ...sample('목포'), tempC: 16.2 }))
    await flushPromises()
    pending['울산'](json(sample('울산')))
    await flushPromises()
    expect(wrapper.text()).toContain('16.2℃')
  })

  it('WEATHER-T03 해제(로그아웃) 뒤 응답도 실패도 무시한다', async () => {
    let finish
    fetch.mockImplementation(() => new Promise((r) => (finish = r)))
    wrapper = mount(WeatherWidget)
    const vm = wrapper.vm
    wrapper.unmount()
    finish(json(sample('울산')))
    await flushPromises()
    expect(vm.weather ?? null).toBeNull()
    wrapper = null
  })

  it('10분마다 재조회하고 해제 시 멈춘다', async () => {
    vi.useFakeTimers()
    wrapper = mount(WeatherWidget)
    await vi.advanceTimersByTimeAsync(10 * 60 * 1000)
    expect(fetch).toHaveBeenCalledTimes(2)
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(10 * 60 * 1000)
    expect(fetch).toHaveBeenCalledTimes(2)
    wrapper = null
    vi.useRealTimers()
  })
})
