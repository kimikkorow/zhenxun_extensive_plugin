#!/usr/bin/env node

/*
 * Read-only Miao SR rule runner.
 *
 * The Miao checkout has no node_modules in the target environment.  SR calc
 * files are deliberately small rule modules, so evaluating them with a
 * read-only Function wrapper is enough.  This file does not import the Miao
 * application and never writes to the checkout or to a profile cache.
 */

import fs from 'node:fs'
import path from 'node:path'
import readline from 'node:readline'

const REVISION = 'afff386eb6b31bc70a98144c3bbfa884eaf5e621'
const root = process.env.MIAO_PLUGIN_ROOT || '/Users/crazy/PycharmProjects/miao-plugin'

const Format = {
  comma (value, digits = 0) {
    const num = Number(value)
    if (!Number.isFinite(num)) return String(value)
    return num.toLocaleString('en-US', { maximumFractionDigits: digits })
  },
  percent (value, digits = 1) {
    const num = Number(value) * 100
    return `${num.toFixed(digits)}%`
  },
  pct (value, digits = 1) {
    return this.percent(value, digits)
  },
  elemName (value) {
    return value
  }
}

// A small logger shim keeps read-only calc rules that log diagnostic values
// executable without loading the Miao application runtime.
const logger = {
  info () {},
  debug () {},
  warn () {},
  error () {}
}

const BREAK_BASE = {
  1: 54, 2: 58, 3: 62, 4: 67.53, 5: 70.51, 6: 73.52, 7: 76.57,
  8: 79.64, 9: 82.74, 10: 85.87, 11: 91.49, 12: 97.07, 13: 102.59,
  14: 108.06, 15: 113.47, 16: 118.84, 17: 124.15, 18: 129.41,
  19: 134.62, 20: 139.77, 21: 149.33, 22: 158.8, 23: 168.18,
  24: 177.46, 25: 186.65, 26: 195.75, 27: 204.75, 28: 213.66,
  29: 222.48, 30: 231.2, 31: 246.43, 32: 261.18, 33: 275.47,
  34: 289.32, 35: 302.73, 36: 315.71, 37: 328.29, 38: 340.47,
  39: 352.26, 40: 363.67, 41: 408.12, 42: 451.79, 43: 494.68,
  44: 536.82, 45: 578.22, 46: 618.92, 47: 658.91, 48: 698.23,
  49: 736.89, 50: 774.9, 51: 871.06, 52: 964.87, 53: 1056.42,
  54: 1145.79, 55: 1233.06, 56: 1318.3, 57: 1401.58, 58: 1482.96,
  59: 1562.52, 60: 1640.31, 61: 1752.32, 62: 1861.9, 63: 1969.12,
  64: 2074.07, 65: 2176.8, 66: 2277.39, 67: 2375.91, 68: 2472.42,
  69: 2566.97, 70: 2659.64, 71: 2780.3, 72: 2898.6, 73: 3014.6,
  74: 3128.37, 75: 3239.98, 76: 3349.47, 77: 3456.92, 78: 3562.38,
  79: 3665.91, 80: 3767.55
}

const BREAK_COEFFICIENT = {
  lightningBreak: 1, fireBreak: 2, windBreak: 1.5,
  physicalBreak: 2, quantumBreak: 0.5, imaginaryBreak: 0.5,
  iceBreak: 1, superBreak: 1
}

const DOT_COEFFICIENT = { shock: 2, burn: 1, windShear: 1, bleed: 1 }

let elationBase
function getElationBase () {
  if (elationBase) return elationBase
  const source = fs.readFileSync(path.join(root, 'models', 'dmg', 'DmgCalcMeta.js'), 'utf8')
  const match = /export const elationBaseDmg\s*=\s*(\{[\s\S]*?\n\})/.exec(source)
  if (!match) throw new Error('Miao elationBaseDmg not found')
  elationBase = Function(`return (${match[1]})`)()
  return elationBase
}

class AttrItem {
  constructor (value = {}) {
    this.base = Number(value.base) || 0
    this.plus = Number(value.plus) || 0
    this.pct = Number(value.pct) || 0
    this.inc = Number(value.inc) || 0
  }

  valueOf () {
    return this.base + this.plus + this.base * this.pct / 100
  }

  toString () {
    return String(this.valueOf())
  }
}

const attrKeys = [
  'a', 'a2', 'a3', 'e', 'e2', 'xe', 'q', 'q2', 'q3', 't', 't2',
  'me', 'me2', 'mt', 'mt1', 'mt2', 'dot', 'break', 'elation'
]

function item (base = 0, plus = 0, pct = 0) {
  return new AttrItem({ base, plus, pct })
}

function number (value, fallback = 0) {
  const ret = Number(value)
  return Number.isFinite(ret) ? ret : fallback
}

function attrValue (value) {
  return number(value)
}

function cloneAttr (attr) {
  const ret = {}
  for (const [key, value] of Object.entries(attr)) {
    if (value instanceof AttrItem) {
      ret[key] = new AttrItem(value)
    } else if (value && typeof value === 'object' && !Array.isArray(value)) {
      ret[key] = cloneAttr(value)
    } else if (Array.isArray(value)) {
      ret[key] = value.slice()
    } else {
      ret[key] = value
    }
  }
  return ret
}

function calcAttrValue (ds) {
  return attrValue(ds)
}

function createAttr (profile, charData, meta) {
  const props = profile.attr || profile['属性'] || {}
  const baseAtk = number(props.baseAtk, number(props.atkBase, number(props['基础攻击力'], 0)))
  const baseHp = number(props.baseHp, number(props.hpBase, number(props['基础生命值'], 0)))
  const baseDef = number(props.baseDef, number(props.defBase, number(props['基础防御力'], 0)))
  const baseSpeed = number(props.baseSpeed, number(props.speedBase, number(props['基础速度'], 0)))
  const atk = number(props.atk, number(props['基础攻击力'], 0) + number(props['额外攻击力'], 0))
  const hp = number(props.hp, number(props['基础生命值'], 0) + number(props['额外生命值'], 0))
  const def = number(props.def, number(props['基础防御力'], 0) + number(props['额外防御力'], 0))
  const speed = number(props.speed, number(props['基础速度'], 0) + number(props['额外速度'], 0))
  const cpctBase = number(props.cpctBase, number(props['基础暴击率'], 0) * 100)
  const cdmgBase = number(props.cdmgBase, number(props['基础暴击伤害'], 0) * 100)
  const cpct = number(props.cpct, cpctBase + number(props['暴击率'], 0) * 100)
  const cdmg = number(props.cdmg, cdmgBase + number(props['暴击伤害'], 0) * 100)
  const dmg = number(props.dmg, number(props['伤害加成'], 0) * 100)
  const stance = number(props.stance, number(props['击破特攻'], 0) * 100)
  const effPct = number(props.effPct, number(props['效果命中'], 0) * 100)
  const effDef = number(props.effDef, number(props['效果抵抗'], 0) * 100)
  const energy = number(props.recharge, number(props['能量恢复效率'], 0) * 100)
  const heal = number(props.heal, number(props['治疗加成'], 0) * 100)
  const joy = number(props.joy, number(props['欢愉度'], 0) * 100)
  const baseAttrs = {
    atk: item(baseAtk, atk - baseAtk),
    hp: item(baseHp, hp - baseHp),
    def: item(baseDef, def - baseDef),
    speed: item(baseSpeed, speed - baseSpeed),
    recharge: item(energy), cpct: item(cpctBase, cpct - cpctBase),
    cdmg: item(cdmgBase, cdmg - cdmgBase), heal: item(heal), dmg: item(dmg),
    enemydmg: item(0), effPct: item(effPct), effDef: item(effDef),
    stance: item(stance), joy: item(joy),
    phy: item(0), coloringDmg: item(0)
  }
  for (const key of attrKeys) {
    baseAttrs[key] = {
      pct: 0, multi: 0, plus: 0, dmg: 0, enemydmg: 0,
      cpct: 0, cdmg: 0, elevated: 0, merrymakes: 0, def: 0, ignore: 0
    }
  }
  baseAttrs.enemy = { def: 0, ignore: 0, phy: 0 }
  baseAttrs.shield = { base: 100, plus: 0, inc: 100 }
  baseAttrs.weapon = meta.weapon || profile.weapon || profile['光锥'] || { name: '', affix: 1 }
  baseAttrs.refine = number(baseAttrs.weapon.affix, number(baseAttrs.weapon.refine, 1)) - 1
  baseAttrs.weaponTypeName = baseAttrs.weapon.type || ''
  baseAttrs.element = charData.elem || profile.element || ''
  baseAttrs.sp = number(charData.sp, 0)
  // DmgAttr keeps a snapshot of static profile values.  A few rules use it
  // to distinguish panel damage/speed from dynamic buffs.
  baseAttrs.staticAttr = {
    atk: new AttrItem(baseAttrs.atk),
    hp: new AttrItem(baseAttrs.hp),
    def: new AttrItem(baseAttrs.def),
    speed: new AttrItem(baseAttrs.speed),
    dmg: { base: 0, plus: dmg, pct: 0 }
  }
  baseAttrs.multi = 0
  baseAttrs.kx = 0
  baseAttrs.fykx = 0
  baseAttrs.elevated = 0
  baseAttrs.merrymakes = 0
  baseAttrs.punchline = 0
  baseAttrs.superBreak = { ignore: 0 }
  return baseAttrs
}

function formatValue (value) {
  if (typeof value === 'string') return value
  if (typeof value === 'number' && Number.isFinite(value)) return String(Math.floor(value))
  return String(value)
}

function applyData (attr, key, value) {
  value = number(value)
  let match = /^(a|a2|a3|e|e2|xe|q|q2|q3|t|t2|me|mt|mt2|dot|break|elation)(Def|Ignore|Dmg|Enemydmg|Plus|Pct|Cpct|Cdmg|Multi|Elevated|Merrymakes)$/.exec(key)
  if (match) {
    const target = attr[match[1]]
    target[match[2].toLowerCase()] += value
    return
  }
  match = /^(mastery|cpct|cdmg|heal|recharge|dmg|enemydmg|phy|coloringDmg|shield|speed|stance|joy|effPct|effDef)(Plus|Pct|Inc)?$/.exec(key)
  if (match) {
    const target = attr[match[1]]
    target[match[2] ? match[2].toLowerCase() : 'plus'] += value
    return
  }
  match = /^(hp|def|atk)(Base|Plus|Pct|Inc)?$/.exec(key)
  if (match) {
    const target = attr[match[1]]
    target[match[2] ? match[2].toLowerCase() : 'plus'] += value
    return
  }
  if (key === 'enemyDef') {
    attr.enemy.def += value
  } else if (key === 'ignore' || key === 'enemyIgnore') {
    attr.enemy.ignore += value
  } else if (['kx', 'fykx', 'multi', 'fyplus', 'fypct', 'fybase', 'fyinc', 'merrymakes', 'punchline'].includes(key)) {
    attr[key] += value
  } else if (key === 'superBreakIgnore') {
    attr.superBreak.ignore += value
  }
}

function buildDataSet (attr, meta, params, talent) {
  return {
    ...meta,
    attr,
    params,
    talent,
    artis: meta.artis,
    refine: attr.refine,
    weaponTypeName: attr.weaponTypeName,
    element: attr.element,
    calc: calcAttrValue
  }
}

function titleValue (title, ds) {
  if (typeof title === 'function') return title(ds)
  return title
}

function evaluateData (data, ds) {
  const ret = {}
  for (const [key, raw] of Object.entries(data || {})) {
    const value = typeof raw === 'function' ? raw(ds) : raw
    if (value === undefined || value === null || (typeof value === 'number' && !Number.isFinite(value))) continue
    ret[key] = value
  }
  return ret
}

function addBuffs (original, buffs, meta, params, talent, selectedTalent = '') {
  const attr = cloneAttr(original)
  const messages = []
  const baseDs = () => buildDataSet(attr, meta, params, talent)
  for (const buff of buffs || []) {
    if (!buff || buff.isStatic) continue
    const ds = baseDs()
    ds.currentTalent = selectedTalent
    ds.artis = meta.artis
    if (buff.check && !buff.check(ds)) continue
    if (buff.cons !== undefined && Number(ds.cons) < Number(buff.cons)) continue
    if (buff.maxCons !== undefined && Number(ds.cons) > Number(buff.maxCons)) continue
    if (buff.tree !== undefined && !ds.trees[`10${buff.tree}`] && !ds.trees[String(buff.tree)]) continue
    let title = titleValue(buff.title, ds)
    const data = evaluateData(buff.data, ds)
    for (const [key, raw] of Object.entries(data)) {
      title = String(title || '').replaceAll(`[${key}]`, Format.comma(raw, 1))
      applyData(attr, key, raw)
    }
    if (title) messages.push(title)
  }
  return { attr, messages }
}

function defenseMultiplier (level, enemyLevel, enemyDef, enemyIgnore) {
  const defdown = Math.min(1, (number(enemyDef) + number(enemyIgnore)) / 100)
  const selfDef = 200 + number(level) * 10
  const enemyDefValue = 200 + number(enemyLevel) * 10
  return selfDef / (selfDef + enemyDefValue * (1 - defdown))
}

function DmgCalc (data) {
  const { attr, ds, level, enemyLv } = data
  const calc = ds.calc
  function calcRet ({ pctNum, talent, ele, basicNum, mode, dynamicData = {} }) {
    let {
      dynamicDmg = 0, dynamicPhy = 0, dynamicCpct = 0,
      dynamicCdmg = 0, dynamicEnemydmg = 0
    } = dynamicData || {}
    let atkNum = calc(attr.atk)
    let multiNum = attr.multi / 100
    let fyplus = attr.fyplus
    let fypct = attr.fypct / 100
    let fybase = attr.fybase
    let fyinc = attr.fyinc / 100
    let dmgNum = 1 + attr.dmg.base / 100 + attr.dmg.plus / 100 + dynamicDmg / 100
    if (ele === 'phy') dmgNum = 1 + attr.phy.base / 100 + attr.phy.plus / 100 + dynamicPhy / 100
    let enemydmgNum = 1 + attr.enemydmg.base / 100 + attr.enemydmg.plus / 100 + dynamicEnemydmg / 100
    let cpctNum = attr.cpct.base / 100 + attr.cpct.plus / 100 + dynamicCpct / 100
    let cdmgNum = attr.cdmg.base / 100 + attr.cdmg.plus / 100 + dynamicCdmg / 100
    let enemyDef = attr.enemy.def / 100
    let enemyIgnore = attr.enemy.ignore / 100
    let plusNum = 0
    pctNum = number(pctNum) * 100
    if (talent) {
      for (const t of String(talent).split(',')) {
        const dsTalent = attr[t]
        if (!dsTalent) continue
        pctNum += dsTalent.pct
        dmgNum += dsTalent.dmg / 100
        enemydmgNum += dsTalent.enemydmg / 100
        cpctNum += dsTalent.cpct / 100
        cdmgNum += dsTalent.cdmg / 100
        enemyDef += dsTalent.def / 100
        enemyIgnore += dsTalent.ignore / 100
        multiNum += dsTalent.multi / 100
        plusNum += dsTalent.plus
      }
    }
    if (ele === 'superBreak') enemyIgnore += attr.superBreak.ignore / 100
    const defNum = defenseMultiplier(level, enemyLv, enemyDef * 100, enemyIgnore * 100)
    const kNum = 1 + attr.kx / 100
    const reduceNum = 0.9
    cpctNum = Math.max(0, Math.min(1, cpctNum))
    if (cpctNum === 0) cdmgNum = 0
    const dmgBase = mode === 'basic' ? number(basicNum) * (1 + multiNum) + plusNum : atkNum * (pctNum / 100) * (1 + multiNum) + plusNum
    const ordinary = (factor = 1, crit = true) => {
      const common = dmgBase * factor * dmgNum * enemydmgNum * defNum * kNum * reduceNum
      return crit
        ? { dmg: common * (1 + cdmgNum), avg: common * (1 + cpctNum * cdmgNum) }
        : { avg: common }
    }
    if (['shock', 'burn', 'windShear', 'bleed', 'entanglement', 'lightningBreak', 'fireBreak', 'windBreak', 'physicalBreak', 'quantumBreak', 'imaginaryBreak', 'iceBreak', 'superBreak'].includes(ele)) {
      const base = BREAK_BASE[Math.max(1, Math.min(80, Math.floor(level)))] || BREAK_BASE[80]
      let coefficient = BREAK_COEFFICIENT[ele] || DOT_COEFFICIENT[ele] || 1
      if (ele === 'entanglement') coefficient = 0.6
      const stanceNum = 1 + calc(attr.stance) / 100
      return { avg: base * coefficient * stanceNum * enemydmgNum * defNum * kNum * reduceNum }
    }
    if (ele === 'elation') {
      const base = getElationBase()[Math.max(1, Math.min(80, Math.floor(level)))]
      const merrymakesNum = 1 + attr.merrymakes / 100
      const joyNum = 1 + attr.joy.base / 100 + attr.joy.plus / 100
      const punchlineNum = attr.punchline
      const punchlineCalc = 1 + punchlineNum * 5 / (punchlineNum + 240)
      const common = base * (pctNum / 100 + multiNum) * merrymakesNum * joyNum * punchlineCalc * defNum * kNum * reduceNum * enemydmgNum
      return { dmg: common * (1 + cdmgNum), avg: common * (1 + cpctNum * cdmgNum) }
    }
    if (ele === 'skillDot') return ordinary(1, false)
    return ordinary()
  }
  const dmgFn = function (pctNum = 0, talent = false, ele = false, basicNum = 0, mode = 'talent', dynamicData = false) {
    return calcRet({ pctNum, talent, ele, basicNum, mode, dynamicData: dynamicData || {} })
  }
  dmgFn.basic = (basicNum = 0, talent = false, ele = false, dynamicData = false) => dmgFn(0, talent, ele, basicNum, 'basic', dynamicData)
  dmgFn.reaction = (ele = false, talent = 'fy') => {
    if (['shock', 'burn', 'windShear', 'bleed'].includes(ele)) talent = 'dot'
    if (['superBreak', 'lightningBreak', 'fireBreak', 'windBreak', 'physicalBreak', 'quantumBreak', 'imaginaryBreak', 'iceBreak'].includes(ele)) talent = 'break'
    return dmgFn(0, talent, ele, 0, 'basic')
  }
  dmgFn.dynamic = (pctNum = 0, talent = false, dynamicData = false, ele = false) => dmgFn(pctNum, talent, ele, 0, 'talent', dynamicData)
  dmgFn.heal = (num) => ({ avg: number(num) * (1 + attr.heal.base / 100 + attr.heal.plus / 100 + attr.heal.inc / 100) })
  dmgFn.shield = (num) => ({ avg: number(num) * (attr.shield.base + attr.shield.plus) / 100 * attr.shield.inc / 100 })
  dmgFn.swirl = () => dmgFn(0, 'fy', 'swirl')
  return dmgFn
}

function evaluateModule (file, defaultOnly = false) {
  const source = fs.readFileSync(file, 'utf8')
    .replace(/^\s*import[^\n]*\n/gm, '')
    .replace(/export\s+const\s+/g, 'const ')
    .replace(/export\s+default\s+/g, 'const __default = ')
  const exports = ['details', 'buffs', 'defParams', 'defDmgIdx', 'defDmgKey', 'mainAttr', 'enemyName', 'createdBy']
  const tail = defaultOnly ? 'return { default: typeof __default === "undefined" ? undefined : __default }' : `return { ${exports.map(key => `${key}: typeof ${key} === 'undefined' ? undefined : ${key}`).join(', ')} }`
  return Function('Format', 'logger', `${source}\n${tail}`)(Format, logger)
}

function characterFile (name) {
  const file = path.join(root, 'resources', 'meta-sr', 'character', name, 'calc.js')
  return fs.existsSync(file) ? file : null
}

const weaponTypes = ['存护', '丰饶', '毁灭', '记忆', '同谐', '虚无', '巡猎', '智识', '欢愉']
let weaponIndex
function buildWeaponIndex () {
  if (weaponIndex) return weaponIndex
  weaponIndex = new Map()
  const file = path.join(root, 'resources', 'meta-sr', 'weapon', 'data.json')
  if (!fs.existsSync(file)) return weaponIndex
  try {
    const data = JSON.parse(fs.readFileSync(file, 'utf8'))
    for (const item of Object.values(data || {})) {
      if (!item?.name || !item.type) continue
      const detailFile = path.join(root, 'resources', 'meta-sr', 'weapon', item.type, item.name, 'data.json')
      let detail = item
      if (fs.existsSync(detailFile)) {
        try { detail = JSON.parse(fs.readFileSync(detailFile, 'utf8')) } catch {}
      }
      weaponIndex.set(item.name, { type: item.type, data: detail })
    }
  } catch {}
  // Keep compatibility with local revisions that do not expose the compact
  // weapon index but retain the per-path data files.
  if (!weaponIndex.size) {
    for (const type of weaponTypes) {
      const dir = path.join(root, 'resources', 'meta-sr', 'weapon', type)
      if (!fs.existsSync(dir)) continue
      for (const item of fs.readdirSync(dir)) {
        const detailFile = path.join(dir, item, 'data.json')
        if (!fs.existsSync(detailFile)) continue
        try {
          const detail = JSON.parse(fs.readFileSync(detailFile, 'utf8'))
          if (detail.name) weaponIndex.set(detail.name, { type, data: detail })
        } catch {}
      }
    }
  }
  return weaponIndex
}

function weaponBuffs (weapon) {
  if (!weapon || !weapon.name) return []
  const found = buildWeaponIndex().get(weapon.name)
  if (!found) return []
  const file = path.join(root, 'resources', 'meta-sr', 'weapon', found.type, 'calc.js')
  if (!fs.existsSync(file)) return []
  const module = evaluateModule(file, true)
  if (typeof module.default !== 'function') return []
  const staticIdx = (idx, key) => ({ isStatic: true, idx, key })
  const keyIdx = (title, key, idx) => {
    if (key && typeof key === 'object') {
      return (tables) => ({ title, data: Object.fromEntries(Object.entries(key).map(([k, i]) => [k, tables[i]])) })
    }
    return { title, idx, key }
  }
  const factoryResult = module.default(staticIdx, keyIdx)
  if (!factoryResult || (typeof factoryResult !== 'object' && typeof factoryResult !== 'function')) {
    throw new TypeError(`weapon config factory for ${weapon.name} returned an invalid value`)
  }
  const rawConfig = factoryResult?.[weapon.name]
  // Most entries are arrays, but older and newer Miao rules also use a single
  // object or factory function for a weapon.  Preserve invalid primitive
  // values as errors instead of turning them into a successful no-op.
  let config
  if (rawConfig === undefined || rawConfig === null) {
    config = []
  } else if (Array.isArray(rawConfig)) {
    config = rawConfig
  } else if (typeof rawConfig === 'object' || typeof rawConfig === 'function') {
    config = [rawConfig]
  } else {
    throw new TypeError(`weapon config for ${weapon.name} is not an object, function, or array`)
  }
  const refine = Math.max(1, Math.min(5, Number(weapon.affix || weapon.refine || weapon['精炼等级'] || 1)))
  const tables = {}
  for (const [idx, values] of Object.entries(found.data.skill?.tables || {})) tables[idx] = values[refine - 1]
  const ret = []
  for (const original of config) {
    let buff = typeof original === 'function' ? original(tables) : { ...original }
    if (!buff || buff.isStatic) continue
    buff = { ...buff, data: { ...(buff.data || {}) } }
    if (buff.idx && buff.key && tables[buff.idx] !== undefined) buff.data[buff.key] = tables[buff.idx]
    if (!buff.title) continue
    if (!String(buff.title).includes('：')) buff.title = `${weapon.name}：${buff.title}`
    ret.push(buff)
  }
  return ret
}

function runPayload (payload) {
  try {
    const result = main(payload)
    if (!result || typeof result !== 'object') {
      throw new TypeError('oracle result is not an object')
    }
    return result
  } catch (error) {
    return {
      ok: false,
      status: 'runner_error',
      revision: REVISION,
      error: String(error?.stack || error)
    }
  }
}

let artifactData
function buildArtifactIndex () {
  if (artifactData) return artifactData
  artifactData = new Map()
  const file = path.join(root, 'resources', 'meta-sr', 'artifact', 'data.json')
  if (!fs.existsSync(file)) return artifactData
  try {
    const data = JSON.parse(fs.readFileSync(file, 'utf8'))
    for (const item of Object.values(data)) if (item?.name) artifactData.set(String(item.id), item.name)
  } catch {}
  return artifactData
}

function artifactBuffs (artis) {
  if (!artis || typeof artis !== 'object') return []
  const module = evaluateModule(path.join(root, 'resources', 'meta-sr', 'artifact', 'calc.js'), true)
  const calc = module.default || {}
  const ret = []
  for (const [rawId, rawCount] of Object.entries(artis)) {
    const name = buildArtifactIndex().get(String(rawId)) || rawId
    const count = Number(rawCount)
    for (const num of (count >= 4 ? [2, 4] : count >= 2 ? [2] : [])) {
      const entries = Array.isArray(calc[name]?.[num]) ? calc[name][num] : [calc[name]?.[num]]
      for (const original of entries) {
        if (!original || original.isStatic) continue
        ret.push({ ...original, data: { ...(original.data || {}) }, title: `${name}${num}：${original.title || ''}` })
      }
    }
  }
  return ret
}

function roleSets (profile) {
  const sets = {}
  const relics = profile.relics || profile.artis || profile['遗器'] || []
  if (Array.isArray(relics)) {
    for (const relic of relics) {
      if (!relic || typeof relic !== 'object') continue
      const id = String(relic.setId || relic.set_id || relic['所属套装'] || relic.name || relic['名称'] || '')
      if (id) sets[id] = (sets[id] || 0) + 1
    }
  } else if (relics && typeof relics === 'object') {
    for (const [rawId, rawCount] of Object.entries(relics)) {
      const count = typeof rawCount === 'number'
        ? rawCount
        : Array.isArray(rawCount)
          ? rawCount.length
          : Number(rawCount?.count ?? rawCount?.数量 ?? 0)
      if (count > 0) sets[String(rawId)] = count
    }
  }
  return sets
}

function talentFor (profile, charData) {
  const levels = { a: 1, a2: 1, e: 1, e2: 1, q: 1, t: 1, me: 1, me2: 1, mt: 1, mt2: 1 }
  for (const row of profile.talents || profile['行迹'] || []) {
    const title = String(row.name || row['名称'] || '')
    const level = Number(row.level || row['等级'] || 1)
    const key = title.includes('普攻') ? 'a' : title.includes('战技') ? 'e' : title.includes('终结') ? 'q' : 't'
    levels[key] = level
  }
  for (const [key, value] of Object.entries(profile.talent || {})) {
    const level = typeof value === 'object' ? value?.level : value
    if (Number.isFinite(Number(level))) levels[key] = Number(level)
  }
  const ret = {}
  for (const [key, block] of Object.entries(charData.talent || {})) {
    if (!block?.tables) continue
    const parent = /^(a|e|q|t|xe|me|mt)[123]$/.exec(key)?.[1]
    const level = levels[parent || key] || levels.a || 1
    ret[key] = {}
    for (const table of Object.values(block.tables)) {
      if (!table?.name || !Array.isArray(table.values)) continue
      ret[key][table.name] = table.values[Math.max(0, Math.min(table.values.length - 1, level - 1))]
    }
  }
  return ret
}

function readCharacterData (name) {
  const file = path.join(root, 'resources', 'meta-sr', 'character', name, 'data.json')
  if (!fs.existsSync(file)) return null
  try { return JSON.parse(fs.readFileSync(file, 'utf8')) } catch { return null }
}

function normalizeDetail (ret) {
  if (!ret || typeof ret !== 'object') return null
  if (ret.avg === undefined && ret.dmg === undefined) return null
  if (ret.dmg === undefined) return [formatValue(ret.avg)]
  return [formatValue(ret.avg), formatValue(ret.dmg)]
}

function main (input) {
  const name = String(input.name || '')
  const file = characterFile(name)
  if (!file) return { ok: false, status: 'no_rule', name, revision: REVISION }
  const charData = readCharacterData(name)
  if (!charData) return { ok: false, status: 'no_data', name, revision: REVISION }
  const module = evaluateModule(file)
  const profile = input.profile || {}
  const level = Number(profile.level || profile['等级'] || 80)
  const cons = Number(profile.cons ?? (Array.isArray(profile['星魂']) ? profile['星魂'].length : 0))
  const talent = talentFor(profile, charData)
  const trees = {}
  const treeInput = profile.trees || profile['行迹节点'] || []
  if (Array.isArray(treeInput)) {
    for (const id of treeInput) trees[String(id)] = true
  } else if (treeInput && typeof treeInput === 'object') {
    for (const [id, enabled] of Object.entries(treeInput)) {
      if (enabled) trees[String(id)] = true
    }
  }
  const promotion = number(profile.promotion, number(profile['晋升'], 0))
  const promotionRequirements = { 1: 2, 2: 4, 3: 6 }
  for (const node of Object.values(charData.treeData || {})) {
    if (!node || node.type !== 'skill') continue
    const idx = Number(node.idx)
    if (promotionRequirements[idx] !== undefined && promotion >= promotionRequirements[idx]) {
      trees[`10${idx}`] = true
    }
  }
  const weapon = profile.weapon || profile['光锥'] || { name: '', affix: 1 }
  const meta = {
    characterName: name,
    uid: profile.uid,
    level,
    cons,
    talent,
    trees,
    weapon: {
      ...weapon,
      name: weapon.name || weapon['名称'],
      type: weapon.type || weapon['类型'],
      affix: weapon.affix || weapon.refine || weapon['精炼等级'] || 1
    },
    artis: roleSets(profile)
  }
  const originalAttr = createAttr(profile, charData, meta)
  const allBuffs = [
    ...(Array.isArray(module.buffs) ? module.buffs : []),
    ...weaponBuffs(meta.weapon),
    ...artifactBuffs(roleSets(profile))
  ].filter(Boolean)
  allBuffs.sort((a, b) => Number(a.sort || 1) - Number(b.sort || 1))
  let defParams = module.defParams || {}
  if (typeof defParams === 'function') defParams = defParams(meta)
  defParams = defParams || {}
  const ret = {}
  const messages = []
  const details = Array.isArray(module.details) ? module.details : []
  for (const detailSource of details) {
    if (!detailSource || detailSource.isStatic) continue
    let detail = detailSource
    if (typeof detail === 'function') detail = detail({ ...buildDataSet(originalAttr, meta, defParams, talent), profile })
    if (!detail || detail.isStatic) continue
    if (detail.cons !== undefined && cons < Number(detail.cons)) continue
    let params = { ...defParams }
    const detailParams = typeof detail.params === 'function' ? detail.params(meta) : (detail.params || {})
    params = { ...params, ...detailParams }
    const calculated = addBuffs(originalAttr, allBuffs, meta, params, talent, detail.talent || '')
    const attr = calculated.attr
    const ds = buildDataSet(attr, meta, params, talent)
    ds.profile = profile
    if (detail.check && !detail.check(ds)) continue
    const dmg = DmgCalc({ ds, attr, level, enemyLv: Number(input.enemyLv || input['敌人等级'] || 103) })
    const basic = detail.dmg ? detail.dmg(ds, dmg) : null
    const values = normalizeDetail(basic)
    if (!values) continue
    const title = titleValue(detail.title, ds) || `伤害${Object.keys(ret).length + 1}`
    ret[String(title)] = values
    messages.push(calculated.messages)
  }
  if (!Object.keys(ret).length) return { ok: false, status: 'calc_failed', name, revision: REVISION, error: '无可输出伤害项目' }
  const defIdx = typeof module.defDmgIdx === 'function' ? module.defDmgIdx(meta) : Number(module.defDmgIdx ?? -1)
  const selected = messages[defIdx >= 0 && defIdx < messages.length ? defIdx : 0] || messages[0] || []
  return {
    ok: true,
    status: 'success',
    name,
    revision: REVISION,
    damage: ret,
    buffs: selected,
    detailCount: Object.keys(ret).length,
    defDmgIdx: defIdx,
    source: file
  }
}

if (process.argv.includes('--ndjson')) {
  const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity })
  lines.on('line', line => {
    let payload
    try {
      payload = JSON.parse(line || '{}')
    } catch (error) {
      process.stdout.write(`${JSON.stringify({ ok: false, status: 'runner_error', revision: REVISION, error: String(error?.stack || error) })}\n`)
      return
    }
    process.stdout.write(`${JSON.stringify(runPayload(payload))}\n`)
  })
} else {
  let input = ''
  process.stdin.setEncoding('utf8')
  process.stdin.on('data', chunk => { input += chunk })
  process.stdin.on('end', () => {
    let payload
    try {
      payload = JSON.parse(input || '{}')
    } catch (error) {
      process.stdout.write(JSON.stringify({ ok: false, status: 'runner_error', revision: REVISION, error: String(error?.stack || error) }))
      process.exitCode = 1
      return
    }
    const result = runPayload(payload)
    process.stdout.write(JSON.stringify(result))
    if (result.status === 'runner_error') process.exitCode = 1
  })
}
