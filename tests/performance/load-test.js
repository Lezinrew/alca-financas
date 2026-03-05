/**
 * K6 Load Test - ALCA FINANÇAS API
 *
 * Usage:
 *   k6 run load-test.js
 *   k6 run --vus 50 --duration 2m load-test.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const dashboardDuration = new Trend('dashboard_duration');
const transactionDuration = new Trend('transaction_duration');

// Test configuration
export let options = {
  stages: [
    { duration: '30s', target: 10 },   // Warm-up: 10 users
    { duration: '1m', target: 50 },    // Ramp-up: 50 users
    { duration: '2m', target: 50 },    // Steady: 50 users
    { duration: '30s', target: 100 },  // Spike: 100 users
    { duration: '1m', target: 50 },    // Recovery: back to 50
    { duration: '30s', target: 0 },    // Cool-down: 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'], // 95% < 500ms, 99% < 1s
    http_req_failed: ['rate<0.01'],                  // < 1% errors
    errors: ['rate<0.01'],
    dashboard_duration: ['p(95)<600'],
    transaction_duration: ['p(95)<400'],
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8001/api';

// Setup function - runs once before test
export function setup() {
  console.log(`🚀 Starting load test against ${BASE_URL}`);

  // Register a test user
  const timestamp = Date.now();
  const registerPayload = JSON.stringify({
    email: `k6-${timestamp}@example.com`,
    password: 'senha123',
    name: 'K6 Load Tester'
  });

  const registerRes = http.post(`${BASE_URL}/auth/register`, registerPayload, {
    headers: { 'Content-Type': 'application/json' },
  });

  check(registerRes, {
    'setup: register successful': (r) => r.status === 201,
    'setup: received token': (r) => r.json('access_token') !== undefined,
  });

  const accessToken = registerRes.json('access_token');

  // Create test data
  const headers = {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
  };

  // Create category
  const categoryPayload = JSON.stringify({
    name: 'Categoria Teste',
    type: 'expense',
    color: '#6366f1',
    icon: 'tag'
  });

  const categoryRes = http.post(`${BASE_URL}/categories`, categoryPayload, { headers });
  const categoryId = categoryRes.json('id');

  // Create account
  const accountPayload = JSON.stringify({
    name: 'Conta Teste',
    type: 'checking',
    initial_balance: 1000.00,
    currency: 'BRL'
  });

  const accountRes = http.post(`${BASE_URL}/accounts`, accountPayload, { headers });
  const accountId = accountRes.json('id');

  console.log('✅ Setup complete - test data created');

  return {
    token: accessToken,
    categoryId: categoryId,
    accountId: accountId,
  };
}

// Main test function - runs for each VU
export default function (data) {
  const headers = {
    'Authorization': `Bearer ${data.token}`,
    'Content-Type': 'application/json',
  };

  // Group 1: Dashboard Operations (READ-heavy)
  group('Dashboard Operations', function () {
    const dashboardStart = Date.now();

    const dashboardRes = http.get(`${BASE_URL}/dashboard`, { headers });

    check(dashboardRes, {
      'dashboard status 200': (r) => r.status === 200,
      'dashboard has balance': (r) => r.json('balance') !== undefined,
    });

    errorRate.add(dashboardRes.status !== 200);
    dashboardDuration.add(Date.now() - dashboardStart);

    sleep(1);
  });

  // Group 2: Transaction Operations (WRITE-heavy)
  group('Transaction Operations', function () {
    // Create transaction
    const transactionStart = Date.now();

    const transactionPayload = JSON.stringify({
      description: `Load Test ${__VU}-${__ITER}`,
      amount: Math.floor(Math.random() * 100) + 10,
      type: 'expense',
      category_id: data.categoryId,
      account_id: data.accountId,
      date: '2024-03-04',
      status: 'paid',
    });

    const createRes = http.post(`${BASE_URL}/transactions`, transactionPayload, { headers });

    check(createRes, {
      'transaction created': (r) => r.status === 201,
    });

    errorRate.add(createRes.status !== 201);
    transactionDuration.add(Date.now() - transactionStart);

    sleep(0.5);

    // List transactions
    const listRes = http.get(`${BASE_URL}/transactions?limit=10`, { headers });

    check(listRes, {
      'transactions listed': (r) => r.status === 200,
      'transactions has data': (r) => r.json('transactions') !== undefined,
    });

    sleep(1);
  });

  // Group 3: Reports Operations (CPU-intensive)
  group('Reports Operations', function () {
    const reportRes = http.get(`${BASE_URL}/reports/overview?type=expenses_by_category`, { headers });

    check(reportRes, {
      'report status 200': (r) => r.status === 200,
      'report has data': (r) => r.json('data') !== undefined,
    });

    sleep(1);
  });

  // Group 4: Account/Category Operations (Mixed READ/WRITE)
  group('Account & Category Operations', function () {
    // List accounts
    const accountsRes = http.get(`${BASE_URL}/accounts`, { headers });

    check(accountsRes, {
      'accounts listed': (r) => r.status === 200,
    });

    sleep(0.5);

    // List categories
    const categoriesRes = http.get(`${BASE_URL}/categories`, { headers });

    check(categoriesRes, {
      'categories listed': (r) => r.status === 200,
    });

    sleep(1);
  });

  // Random sleep between iterations
  sleep(Math.random() * 2 + 1);
}

// Teardown function - runs once after test
export function teardown(data) {
  console.log('🧹 Cleaning up test data...');

  const headers = {
    'Authorization': `Bearer ${data.token}`,
    'Content-Type': 'application/json',
  };

  // Clear all data
  http.post(`${BASE_URL}/auth/data/clear`, '{}', { headers });

  console.log('✅ Teardown complete');
}

// Handle test summary
export function handleSummary(data) {
  console.log('\n📊 LOAD TEST SUMMARY');
  console.log('====================');
  console.log(`Duration: ${data.state.testRunDurationMs / 1000}s`);
  console.log(`Requests: ${data.metrics.http_reqs.values.count}`);
  console.log(`Failed Requests: ${data.metrics.http_req_failed.values.passes || 0}`);
  console.log(`Avg Response Time: ${data.metrics.http_req_duration.values.avg.toFixed(2)}ms`);
  console.log(`P95 Response Time: ${data.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms`);
  console.log(`P99 Response Time: ${data.metrics.http_req_duration.values['p(99)'].toFixed(2)}ms`);

  return {
    'stdout': JSON.stringify(data, null, 2),
    'summary.json': JSON.stringify(data),
  };
}
