<template>
  <div class="market-view">
    <!-- Sidebar -->
    <div class="sidebar">
      <div class="search-box">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索股票代码/名称..."
          @input="filterStocks"
        />
      </div>
      <div class="stock-list">
        <div
          v-for="stock in filteredStocks"
          :key="stock.symbol"
          class="stock-item"
          :class="{ active: currentSymbol === stock.symbol }"
          @click="selectStock(stock)"
        >
          <span class="symbol">{{ stock.symbol }}</span>
          <span class="name">{{ stock.name }}</span>
        </div>
      </div>
    </div>

    <!-- Main Chart Area -->
    <div class="chart-container">
      <div v-if="loading" class="loading-overlay">加载中...</div>
      <div v-if="error" class="error-overlay">{{ error }}</div>
      <div ref="chartRef" class="echarts-dom"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue';
import * as echarts from 'echarts';
import axios from 'axios';

// State
const stocks = ref([]);
const searchQuery = ref('');
const currentSymbol = ref('');
const chartInstance = ref(null);
const chartRef = ref(null);
const loading = ref(false);
const error = ref(null);

// API Base URL (adjust if needed)
const API_BASE = 'http://localhost:8000';

// Computed
const filteredStocks = computed(() => {
  if (!searchQuery.value) return stocks.value;
  const query = searchQuery.value.toLowerCase();
  return stocks.value.filter(s =>
    s.symbol.includes(query) || s.name.toLowerCase().includes(query)
  );
});

// Methods
const fetchStocks = async () => {
  try {
    const res = await axios.get(`${API_BASE}/stocks/list`);
    stocks.value = res.data;
    if (stocks.value.length > 0) {
      selectStock(stocks.value[0]);
    }
  } catch (err) {
    console.error("Failed to fetch stock list:", err);
    error.value = "无法加载股票列表";
  }
};

const selectStock = async (stock) => {
  if (currentSymbol.value === stock.symbol) return;
  currentSymbol.value = stock.symbol;
  await loadChartData(stock.symbol);
};

const loadChartData = async (symbol) => {
  loading.value = true;
  error.value = null;
  try {
    const res = await axios.get(`${API_BASE}/stocks/${symbol}/kline`);
    const data = res.data.data;
    renderChart(symbol, data);
  } catch (err) {
    console.error("Failed to fetch kline data:", err);
    error.value = "无法加载K线数据";
  } finally {
    loading.value = false;
  }
};

const renderChart = (symbol, data) => {
  if (!chartRef.value) return;

  if (chartInstance.value) {
    chartInstance.value.dispose();
  }

  chartInstance.value = echarts.init(chartRef.value);

  // Extract data arrays
  const dates = data.map(item => item.date);
  const klineData = data.map(item => [item.open, item.close, item.low, item.high]);
  const volumes = data.map(item => item.volume);
  const volColors = data.map(item => item.close > item.open ? '#ef232a' : '#14b143');
  const ma20 = data.map(item => item.ma20);
  const volMa5 = data.map(item => item.vol_ma5);
  const macd = data.map(item => item.macd);
  const diff = data.map(item => item.diff);
  const dea = data.map(item => item.dea);
  const k = data.map(item => item.k);
  const d = data.map(item => item.d);
  const j = data.map(item => item.j);

  const option = {
    title: { text: `${symbol} K线图`, left: 'center' },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    axisPointer: { link: { xAxisIndex: 'all' } },
    grid: [
      { left: '10%', right: '5%', height: '40%', top: '10%' }, // Grid 0: K-line
      { left: '10%', right: '5%', height: '10%', top: '55%' }, // Grid 1: Volume
      { left: '10%', right: '5%', height: '12%', top: '68%' }, // Grid 2: MACD
      { left: '10%', right: '5%', height: '12%', top: '83%' }  // Grid 3: KDJ
    ],
    xAxis: [
      { type: 'category', data: dates, scale: true, boundaryGap: false, axisLine: { onZero: false }, splitLine: { show: false }, min: 'dataMin', max: 'dataMax', gridIndex: 0 },
      { type: 'category', data: dates, gridIndex: 1, show: false },
      { type: 'category', data: dates, gridIndex: 2, show: false },
      { type: 'category', data: dates, gridIndex: 3, show: false }
    ],
    yAxis: [
      { scale: true, splitArea: { show: true }, gridIndex: 0 },
      { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisTick: { show: false } },
      { scale: true, gridIndex: 2, splitNumber: 2, axisLabel: { show: false }, axisTick: { show: false } },
      { scale: true, gridIndex: 3, splitNumber: 2, axisLabel: { show: false }, axisTick: { show: false } }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, 2, 3], start: 80, end: 100 },
      { show: true, xAxisIndex: [0, 1, 2, 3], type: 'slider', top: '96%', start: 80, end: 100 }
    ],
    series: [
      // Grid 0: K-line + MA20
      {
        name: '日K',
        type: 'candlestick',
        data: klineData,
        itemStyle: {
          color: '#ef232a',
          color0: '#14b143',
          borderColor: '#ef232a',
          borderColor0: '#14b143'
        },
        xAxisIndex: 0,
        yAxisIndex: 0
      },
      {
        name: 'MA20',
        type: 'line',
        data: ma20,
        smooth: true,
        lineStyle: { opacity: 0.5 },
        xAxisIndex: 0,
        yAxisIndex: 0
      },

      // Grid 1: Volume
      {
        name: 'Volume',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: {
          color: (params) => volColors[params.dataIndex]
        }
      },
      {
        name: 'VOL_MA5',
        type: 'line',
        data: volMa5,
        smooth: true,
        xAxisIndex: 1,
        yAxisIndex: 1
      },

      // Grid 2: MACD
      {
        name: 'MACD',
        type: 'bar',
        xAxisIndex: 2,
        yAxisIndex: 2,
        data: macd,
        itemStyle: {
          color: (params) => {
            return params.value > 0 ? '#ef232a' : '#14b143';
          }
        }
      },
      {
        name: 'DIFF',
        type: 'line',
        xAxisIndex: 2,
        yAxisIndex: 2,
        data: diff
      },
      {
        name: 'DEA',
        type: 'line',
        xAxisIndex: 2,
        yAxisIndex: 2,
        data: dea
      },

      // Grid 3: KDJ
      {
        name: 'K',
        type: 'line',
        xAxisIndex: 3,
        yAxisIndex: 3,
        data: k
      },
      {
        name: 'D',
        type: 'line',
        xAxisIndex: 3,
        yAxisIndex: 3,
        data: d
      },
      {
        name: 'J',
        type: 'line',
        xAxisIndex: 3,
        yAxisIndex: 3,
        data: j
      }
    ]
  };

  chartInstance.value.setOption(option);
};

// Resize chart on window resize
window.addEventListener('resize', () => {
  chartInstance.value && chartInstance.value.resize();
});

onMounted(() => {
  fetchStocks();
});

</script>

<style scoped>
.market-view {
  display: flex;
  height: 100%;
}

.sidebar {
  width: 250px;
  background: #fff;
  border-right: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
}

.search-box {
  padding: 1rem;
  border-bottom: 1px solid #eee;
}

.search-box input {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.stock-list {
  flex: 1;
  overflow-y: auto;
}

.stock-item {
  padding: 0.8rem 1rem;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid #f5f5f5;
}

.stock-item:hover {
  background-color: #f0f9ff;
}

.stock-item.active {
  background-color: #e6f7ff;
  border-left: 4px solid #1890ff;
}

.chart-container {
  flex: 1;
  position: relative;
  background: #fff;
}

.echarts-dom {
  width: 100%;
  height: 100%;
}

.loading-overlay, .error-overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.8);
  z-index: 10;
  font-size: 1.2rem;
}

.error-overlay {
  color: red;
}
</style>
