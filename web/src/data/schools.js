// 七所梦校配置：校徽、校园雪景、主题色、校训
import logoTsinghua from '../assets/schools/logo-tsinghua.jpg';
import logoPku from '../assets/schools/logo-pku.jpg';
import logoNju from '../assets/schools/logo-nju.jpg';
import logoFudan from '../assets/schools/logo-fudan.jpg';
import logoSjtu from '../assets/schools/logo-sjtu.jpg';
import logoUstc from '../assets/schools/logo-ustc.jpg';
import logoZju from '../assets/schools/logo-zju.jpg';
import viewTsinghua from '../assets/schools/view-tsinghua.jpg';
import viewPku from '../assets/schools/view-pku.jpg';
import viewNju from '../assets/schools/view-nju.jpg';
import viewFudan from '../assets/schools/view-fudan.jpg';
import viewSjtu from '../assets/schools/view-sjtu.jpg';
import viewUstc from '../assets/schools/view-ustc.jpg';
import viewZju from '../assets/schools/view-zju.jpg';

export const SCHOOLS = [
  {
    key: 'tsinghua',
    name: '清华大学',
    short: '清华',
    city: '北京',
    logo: logoTsinghua,
    view: viewTsinghua,
    color: '#7c3aed',
    motto: '自强不息，厚德载物',
  },
  {
    key: 'pku',
    name: '北京大学',
    short: '北大',
    city: '北京',
    logo: logoPku,
    view: viewPku,
    color: '#a3262e',
    motto: '思想自由，兼容并包',
  },
  {
    key: 'nju',
    name: '南京大学',
    short: '南大',
    city: '南京',
    logo: logoNju,
    view: viewNju,
    color: '#7e3ff2',
    motto: '诚朴雄伟，励学敦行',
  },
  {
    key: 'fudan',
    name: '复旦大学',
    short: '复旦',
    city: '上海',
    logo: logoFudan,
    view: viewFudan,
    color: '#0e419c',
    motto: '博学而笃志，切问而近思',
  },
  {
    key: 'sjtu',
    name: '上海交通大学',
    short: '上交',
    city: '上海',
    logo: logoSjtu,
    view: viewSjtu,
    color: '#b32222',
    motto: '饮水思源，爱国荣校',
  },
  {
    key: 'ustc',
    name: '中国科学技术大学',
    short: '中科大',
    city: '合肥',
    logo: logoUstc,
    view: viewUstc,
    color: '#16407f',
    motto: '红专并进，理实交融',
  },
  {
    key: 'zju',
    name: '浙江大学',
    short: '浙大',
    city: '杭州',
    logo: logoZju,
    view: viewZju,
    color: '#0058a8',
    motto: '求是创新',
  },
];

export const SCHOOL_MAP = Object.fromEntries(SCHOOLS.map((s) => [s.key, s]));

export const DEFAULT_SCHOOL_KEY = 'fudan';

// 考研初试日期（2028 考研，初试 2027-12-25）
export const EXAM_DATE = '2027-12-25';
