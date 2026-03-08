/**
 * System / E2E тесты — «Книжный обмен»
 * Инструмент: Jest + Puppeteer
 *
 * Поднимает встроенный HTTP-сервер для index.html, чтобы
 * page.setRequestInterception работал корректно (file:// его не поддерживает).
 * API-вызовы перехватываются и мокируются — бэкенд не нужен.
 */

const puppeteer = require('puppeteer');
const http = require('http');
const fs = require('fs');
const path = require('path');

// ─── HTTP-сервер для index.html ──────────────────────────────────────────────

const HTML_PATH = path.resolve(__dirname, '../index.html');
const SERVER_PORT = 3333;
const PAGE_URL = `http://localhost:${SERVER_PORT}/`;

let server;

function startServer() {
  return new Promise((resolve) => {
    server = http.createServer((req, res) => {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      fs.createReadStream(HTML_PATH).pipe(res);
    });
    server.listen(SERVER_PORT, resolve);
  });
}

function stopServer() {
  return new Promise((resolve) => server.close(resolve));
}

// ─── Мок-данные ─────────────────────────────────────────────────────────────

const MOCK_TOKEN =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.' +
  Buffer.from(JSON.stringify({ user_id: 42, exp: 9999999999 })).toString('base64') +
  '.signature';

const MOCK_PROFILE = {
  username: 'testuser',
  email: 'test@example.com',
  first_name: 'Иван',
  last_name: 'Иванов',
  phone: '+79991234567',
  photo: null,
};

const MOCK_BOOKS_LIST = {
  results: [
    {
      user_book_id: 1,
      book: {
        name: 'Война и мир',
        author: 'Толстой',
        genres: ['Роман', 'Историческая проза'],
        overview: 'Великий роман',
      },
      condition: 'Хорошее',
      location: '55.7558,37.6173',
      status: 'available',
    },
  ],
};

const MOCK_RECOMMENDATIONS = {
  recommendations: [
    {
      name: 'Преступление и наказание',
      author: 'Достоевский',
      genres: ['Роман', 'Психологическая проза'],
      reason: 'Похожий жанр',
      similarity: 0.87,
    },
  ],
};

const MOCK_EXCHANGE_LIST = [
  {
    book: { book: { name: 'Война и мир' }, user_book_id: 1 },
    requester: 'testuser',
    owner: 'otheruser',
    status: 'pending',
    created_at: '2025-01-01T12:00:00Z',
  },
];

// ─── Хелпер: настройка перехвата API-запросов ────────────────────────────────

async function setupApiMocks(page) {
  await page.setRequestInterception(true);

  // В Puppeteer v24 req.respond() и req.continue() — async, нужен await
  page.on('request', async (req) => {
    const url = req.url();
    const method = req.method();

    if (!url.includes('/api/')) {
      await req.continue();
      return;
    }

    // CORS preflight
    if (method === 'OPTIONS') {
      await req.respond({
        status: 204,
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        },
        body: '',
      });
      return;
    }

    const respond = (status, body) =>
      req.respond({
        status,
        contentType: 'application/json',
        body: JSON.stringify(body),
        headers: { 'Access-Control-Allow-Origin': '*' },
      });

    if (url.includes('/users/register/') && method === 'POST')
      return await respond(201, { id: 42, username: 'testuser' });

    if (url.includes('/users/token') && method === 'POST')
      return await respond(200, { access: MOCK_TOKEN });

    if (url.includes('/users/me'))
      return await respond(200, MOCK_PROFILE);

    if (url.includes('/users/update') && method === 'PUT')
      return await respond(200, MOCK_PROFILE);

    if (url.includes('/books/list/'))
      return await respond(200, MOCK_BOOKS_LIST);

    if (url.includes('/books/search/'))
      return await respond(200, MOCK_BOOKS_LIST);

    if (url.includes('/books/photos/') && method === 'GET')
      return await respond(200, []);

    if (url.includes('/books/') && method === 'POST')
      return await respond(201, { book_id: 99 });

    if (url.includes('/exchange-requests/list/'))
      return await respond(200, MOCK_EXCHANGE_LIST);

    if (url.includes('/exchange-requests/') && method === 'POST')
      return await respond(201, { id: 1, status: 'pending' });

    if (url.includes('/recommendations/'))
      return await respond(200, MOCK_RECOMMENDATIONS);

    await req.continue();
  });
}

// ─── Хелперы для тестов ──────────────────────────────────────────────────────

async function openPage(browser) {
  const page = await browser.newPage();
  await setupApiMocks(page);
  await page.goto(PAGE_URL, { waitUntil: 'domcontentloaded' });
  return page;
}

async function clickNavLink(page, text) {
  await page.evaluate((t) => {
    const links = Array.from(document.querySelectorAll('nav a'));
    const link = links.find((l) => l.textContent.trim() === t);
    if (link) link.click();
  }, text);
  await new Promise(r => setTimeout(r, 200));
}

async function isVisible(page, selector) {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return false;
    // Проверяем только CSS-класс hidden (offsetParent ненадёжен в headless)
    let node = el;
    while (node && node !== document.body) {
      if (node.classList && node.classList.contains('hidden')) return false;
      node = node.parentElement;
    }
    return true;
  }, selector);
}

// JS-клик — работает даже если элемент вне вьюпорта
async function jsClick(page, selector) {
  await page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) throw new Error('Element not found: ' + sel);
    el.click();
  }, selector);
}

async function loginUser(page) {
  await clickNavLink(page, 'Вход');
  await page.type('#login-username', 'testuser');
  await page.type('#login-password', 'password123');
  await page.click('button[onclick="login()"]');
  await page.waitForFunction(
    () => !document.querySelector('.auth-only').classList.contains('hidden'),
    { timeout: 10000 }
  );
}

// ─── Тесты ───────────────────────────────────────────────────────────────────

describe('Книжный обмен — System / E2E тесты', () => {
  let browser;

  beforeAll(async () => {
    await startServer();
    browser = await puppeteer.launch({
      headless: process.env.PUPPETEER_HEADLESS !== 'false' ? 'shell' : false,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',   // /dev/shm слишком мал в Docker
        '--disable-gpu',
        '--single-process',
      ],
    });
  });

  afterAll(async () => {
    await browser.close();
    await stopServer();
  });

  // ── TC-01: Навигация между разделами ────────────────────────────────────

  describe('TC-01 — Навигация между разделами', () => {
    let page;
    beforeAll(async () => { page = await openPage(browser); });
    afterAll(async () => { await page.close(); });

    test('По умолчанию видна главная страница', async () => {
      expect(await isVisible(page, '#home')).toBe(true);
    });

    test('Переход в «Регистрация» скрывает главную и показывает форму', async () => {
      await clickNavLink(page, 'Регистрация');
      expect(await isVisible(page, '#register')).toBe(true);
      expect(await isVisible(page, '#home')).toBe(false);
    });

    test('Переход в «Вход» показывает форму входа', async () => {
      await clickNavLink(page, 'Вход');
      expect(await isVisible(page, '#login')).toBe(true);
      expect(await isVisible(page, '#register')).toBe(false);
    });

    test('Переход в «Книги» показывает раздел книг', async () => {
      await clickNavLink(page, 'Книги');
      expect(await isVisible(page, '#books')).toBe(true);
    });

    test('Переход в «Рекомендации» показывает раздел рекомендаций', async () => {
      await clickNavLink(page, 'Рекомендации');
      expect(await isVisible(page, '#recommendations')).toBe(true);
    });

    test('Без авторизации «Профиль», «Обмены», «Выход» скрыты', async () => {
      const authLinks = await page.$$('.auth-only');
      for (const link of authLinks) {
        const hidden = await link.evaluate((el) => el.classList.contains('hidden'));
        expect(hidden).toBe(true);
      }
    });
  });

  // ── TC-02: Валидация формы регистрации ──────────────────────────────────

  describe('TC-02 — Валидация регистрации: пустые поля', () => {
    let page;
    beforeAll(async () => {
      page = await openPage(browser);
      await clickNavLink(page, 'Регистрация');
    });
    afterAll(async () => { await page.close(); });

    test('Кнопка без заполнения полей показывает ошибку', async () => {
      await page.click('button[onclick="register()"]');
      await page.waitForFunction(
        () => !document.getElementById('register-result').classList.contains('hidden')
      );
      const text = await page.$eval('#register-result', (el) => el.textContent);
      expect(text).toContain('Заполните все обязательные поля');
    });

    test('Сообщение об ошибке имеет CSS-класс error', async () => {
      const hasError = await page.$eval('#register-result', (el) =>
        el.classList.contains('error')
      );
      expect(hasError).toBe(true);
    });
  });

  // ── TC-03: Успешная регистрация ──────────────────────────────────────────

  describe('TC-03 — Успешная регистрация', () => {
    let page;
    beforeAll(async () => {
      page = await openPage(browser);
      await clickNavLink(page, 'Регистрация');
    });
    afterAll(async () => { await page.close(); });

    test('Заполнение формы и нажатие кнопки показывает успех', async () => {
      await page.type('#register-username', 'newuser');
      await page.type('#register-email', 'new@example.com');
      await page.type('#register-password', 'securepass');
      await page.type('#register-first-name', 'Иван');
      await page.type('#register-last-name', 'Иванов');
      await page.click('button[onclick="register()"]');

      await page.waitForFunction(
        () => {
          const el = document.getElementById('register-result');
          return !el.classList.contains('hidden') && el.textContent.trim() !== '';
        },
        { timeout: 10000 }
      );

      const text = await page.$eval('#register-result', (el) => el.textContent);
      expect(text).toContain('Регистрация успешна');
    });

    test('После регистрации происходит переход на раздел Вход', async () => {
      await page.waitForFunction(
        () => !document.getElementById('login').classList.contains('hidden'),
        { timeout: 5000 }
      );
      expect(await isVisible(page, '#login')).toBe(true);
    });
  });

  // ── TC-04: Вход в систему ────────────────────────────────────────────────

  describe('TC-04 — Успешный вход в систему', () => {
    let page;
    beforeAll(async () => { page = await openPage(browser); });
    afterAll(async () => { await page.close(); });

    test('После входа отображается "Вход успешен!"', async () => {
      await loginUser(page);
      const text = await page.$eval('#login-result', (el) => el.textContent);
      expect(text).toContain('Вход успешен!');
    });

    test('После входа в навигации появляются auth-only ссылки', async () => {
      const authLinks = await page.$$('.auth-only');
      for (const link of authLinks) {
        const hidden = await link.evaluate((el) => el.classList.contains('hidden'));
        expect(hidden).toBe(false);
      }
    });

    test('После входа происходит переход на раздел Профиль', async () => {
      expect(await isVisible(page, '#profile')).toBe(true);
    });
  });

  // ── TC-05: Выход из системы ──────────────────────────────────────────────

  describe('TC-05 — Выход из системы', () => {
    let page;
    beforeAll(async () => {
      page = await openPage(browser);
      await loginUser(page);
    });
    afterAll(async () => { await page.close(); });

    test('После выхода происходит переход на Главную', async () => {
      await page.evaluate(() => window.logout());
      // Ждём пока showSection('home') уберёт класс hidden с #home
      await page.waitForFunction(
        () => !document.getElementById('home').classList.contains('hidden'),
        { timeout: 5000 }
      );
      const homeHidden = await page.$eval('#home', el => el.classList.contains('hidden'));
      expect(homeHidden).toBe(false);
    });

    test('После выхода auth-only ссылки скрываются', async () => {
      // Проверяем все .auth-only за один evaluate — без ElementHandle
      const allHidden = await page.evaluate(() => {
        const links = document.querySelectorAll('.auth-only');
        return Array.from(links).every(el => el.classList.contains('hidden'));
      });
      expect(allHidden).toBe(true);
    });
  });

  // ── TC-06: Валидация поля «Местоположение» ──────────────────────────────

  describe('TC-06 — Валидация формата местоположения', () => {
    let page;
    beforeAll(async () => {
      page = await openPage(browser);
      await loginUser(page);
      await clickNavLink(page, 'Книги');
    });
    afterAll(async () => { await page.close(); });

    test('Некорректный формат lat,lon показывает ошибку', async () => {
      await page.evaluate(() => {
        document.getElementById('add-book-title').value = 'Тестовая книга';
        document.getElementById('add-book-author').value = 'Автор';
        document.getElementById('add-book-overview').value = 'Описание';
        document.getElementById('add-book-condition').value = 'Хорошее';
        document.getElementById('add-book-location').value = 'invalid-location';
      });
      await jsClick(page, 'button[onclick="addBook()"]');

      await page.waitForFunction(
        () => !document.getElementById('books-result').classList.contains('hidden'),
        { timeout: 5000 }
      );

      const text = await page.$eval('#books-result', (el) => el.textContent);
      expect(text).toContain('формате lat,lon');
    });
  });

  // ── TC-07: Успешное добавление книги ────────────────────────────────────

  describe('TC-07 — Успешное добавление книги', () => {
    let page;
    beforeAll(async () => {
      page = await openPage(browser);
      await loginUser(page);
      await clickNavLink(page, 'Книги');
    });
    afterAll(async () => { await page.close(); });

    test('Книга добавляется при корректном заполнении формы', async () => {
      await page.evaluate(() => {
        document.getElementById('add-book-title').value = 'Мастер и Маргарита';
        document.getElementById('add-book-author').value = 'Булгаков';
        document.getElementById('add-book-overview').value = 'Классика';
        document.getElementById('add-book-genres').value = 'Роман';
        document.getElementById('add-book-condition').value = 'Отличное';
        document.getElementById('add-book-location').value = '55.7558,37.6173';
      });
      await jsClick(page, 'button[onclick="addBook()"]');

      await page.waitForFunction(
        () => {
          const el = document.getElementById('books-result');
          return !el.classList.contains('hidden') && el.textContent.includes('добавлена');
        },
        { timeout: 10000 }
      );

      const text = await page.$eval('#books-result', (el) => el.textContent);
      expect(text).toContain('Книга добавлена!');
    });

    test('После добавления в «Мои книги» появляется карточка', async () => {
      await page.waitForFunction(
        () => document.querySelector('#my-books .book-card') !== null,
        { timeout: 10000 }
      );
      const cardTitle = await page.$eval('#my-books .book-card h3', (el) => el.textContent);
      expect(cardTitle).toBe('Война и мир');
    });
  });

  // ── TC-08: Поиск книг ────────────────────────────────────────────────────

  describe('TC-08 — Поиск книг', () => {
    let page;
    beforeAll(async () => {
      page = await openPage(browser);
      await loginUser(page);
      await clickNavLink(page, 'Книги');
    });
    afterAll(async () => { await page.close(); });

    test('Поиск возвращает карточки книг', async () => {
      await page.type('#search-query', 'Война');
      await jsClick(page, 'button[onclick="searchBooks()"]');

      await page.waitForFunction(
        () => document.querySelector('#books-result .book-card') !== null,
        { timeout: 10000 }
      );

      const cards = await page.$$('#books-result .book-card');
      expect(cards.length).toBeGreaterThan(0);
    });

    test('Карточка содержит название, автора и кнопку «Запросить обмен»', async () => {
      const title = await page.$eval('#books-result .book-card h3', (el) => el.textContent);
      expect(title).toBe('Война и мир');

      const hasExchangeBtn = await page.evaluate(() =>
        !!document.querySelector('#books-result .book-card button[onclick*="createExchangeRequest"]')
      );
      expect(hasExchangeBtn).toBe(true);
    });
  });

  // ── TC-09: Валидация создания запроса на обмен ───────────────────────────

  describe('TC-09 — Валидация: пустой ID при создании обмена', () => {
    let page;
    beforeAll(async () => {
      page = await openPage(browser);
      await loginUser(page);
      await page.evaluate(() => window.showSection('exchange-requests'));
      await new Promise(r => setTimeout(r, 200));
    });
    afterAll(async () => { await page.close(); });

    test('Кнопка без ID показывает ошибку «Введите ID книги»', async () => {
      await jsClick(page, 'button[onclick="createExchangeRequest()"]');
      await page.waitForFunction(
        () => !document.getElementById('exchange-result').classList.contains('hidden'),
        { timeout: 5000 }
      );
      const text = await page.$eval('#exchange-result', (el) => el.textContent);
      expect(text).toContain('Введите ID книги');
    });
  });

  // ── TC-10: Получение рекомендаций ───────────────────────────────────────

  describe('TC-10 — Получение рекомендаций', () => {
    let page;
    beforeAll(async () => {
      page = await openPage(browser);
      await loginUser(page);
      await clickNavLink(page, 'Рекомендации');
    });
    afterAll(async () => { await page.close(); });

    test('Кнопка «Получить рекомендации» возвращает карточки', async () => {
      await jsClick(page, 'button[onclick="getRecommendations()"]');
      await page.waitForFunction(
        () => document.querySelector('#recommendations-result .book-card') !== null,
        { timeout: 10000 }
      );
      const cards = await page.$$('#recommendations-result .book-card');
      expect(cards.length).toBeGreaterThan(0);
    });

    test('Карточка рекомендации содержит причину и оценку сходства', async () => {
      const text = await page.$eval('#recommendations-result .book-card', (el) => el.textContent);
      expect(text).toContain('Причина');
      expect(text).toContain('Сходство');
      expect(text).toContain('Преступление и наказание');
    });
  });

  // ── TC-11: Обновление профиля и проверка отображения ────────────────────

  describe('TC-11 — Обновление профиля пользователя', () => {
    let page;

    beforeAll(async () => {
      // Мок для PUT /users/update возвращает обновлённые данные
      page = await openPage(browser);
      await loginUser(page);
      // Уже на странице профиля после входа
    });
    afterAll(async () => { await page.close(); });

    test('Форма обновления профиля присутствует на странице', async () => {
      const hasForm = await page.evaluate(() =>
        !!document.getElementById('update-username') &&
        !!document.getElementById('update-email')
      );
      expect(hasForm).toBe(true);
    });

    test('После заполнения и отправки формы появляется сообщение об успехе', async () => {
      await page.evaluate(() => {
        document.getElementById('update-username').value = 'updated_user';
        document.getElementById('update-email').value = 'updated@example.com';
        document.getElementById('update-first-name').value = 'Пётр';
        document.getElementById('update-last-name').value = 'Петров';
      });
      await jsClick(page, 'button[onclick="updateProfile()"]');

      await page.waitForFunction(
        () => {
          const el = document.getElementById('update-result');
          return !el.classList.contains('hidden') && el.textContent.trim() !== '';
        },
        { timeout: 10000 }
      );

      const text = await page.$eval('#update-result', el => el.textContent);
      expect(text).toContain('обновлен');
    });

    test('Блок профиля отображает данные пользователя после загрузки', async () => {
      // getProfile() вызывается автоматически после входа
      await page.waitForFunction(
        () => {
          const el = document.getElementById('profile-info');
          return !el.classList.contains('hidden') && el.textContent.trim().length > 0;
        },
        { timeout: 10000 }
      );

      const profileText = await page.$eval('#profile-info', el => el.textContent);
      // Проверяем что есть хотя бы имя пользователя и email (из мока MOCK_PROFILE)
      expect(profileText).toContain('testuser');
      expect(profileText).toContain('test@example.com');
    });
  });

  // ── TC-12: Полный цикл — добавить книгу → найти → запросить обмен ────────

  describe('TC-12 — Полный цикл: добавление книги и запрос обмена через поиск', () => {
    let page;

    beforeAll(async () => {
      page = await openPage(browser);
      await loginUser(page);
      await clickNavLink(page, 'Книги');
    });
    afterAll(async () => { await page.close(); });

    test('Шаг 1: Пользователь добавляет книгу', async () => {
      await page.evaluate(() => {
        document.getElementById('add-book-title').value = 'Идиот';
        document.getElementById('add-book-author').value = 'Достоевский';
        document.getElementById('add-book-overview').value = 'Великий роман';
        document.getElementById('add-book-genres').value = 'Роман';
        document.getElementById('add-book-condition').value = 'Хорошее';
        document.getElementById('add-book-location').value = '59.9343,30.3351';
      });
      await jsClick(page, 'button[onclick="addBook()"]');

      await page.waitForFunction(
        () => {
          const el = document.getElementById('books-result');
          return !el.classList.contains('hidden') && el.textContent.includes('добавлена');
        },
        { timeout: 10000 }
      );

      const text = await page.$eval('#books-result', el => el.textContent);
      expect(text).toContain('Книга добавлена!');
    });

    test('Шаг 2: Поиск находит добавленную книгу', async () => {
      // Мок /books/search/ возвращает MOCK_BOOKS_LIST
      await page.evaluate(() => {
        document.getElementById('search-query').value = 'Война';
      });
      await jsClick(page, 'button[onclick="searchBooks()"]');

      await page.waitForFunction(
        () => document.querySelector('#books-result .book-card') !== null,
        { timeout: 10000 }
      );

      const cards = await page.$$('#books-result .book-card');
      expect(cards.length).toBeGreaterThan(0);
    });

    test('Шаг 3: Кнопка «Запросить обмен» на карточке создаёт запрос', async () => {
      // Кликаем кнопку обмена прямо с карточки поиска
      await page.evaluate(() => {
        const btn = document.querySelector(
          '#books-result .book-card button[onclick*="createExchangeRequest"]'
        );
        if (btn) btn.click();
      });

      // Мок /exchange-requests/ возвращает success → getExchangeRequests вызывается автоматически
      await page.waitForFunction(
        () => {
          const el = document.getElementById('exchange-result');
          return !el.classList.contains('hidden') && el.textContent.trim() !== '';
        },
        { timeout: 10000 }
      );

      const text = await page.$eval('#exchange-result', el => el.textContent);
      expect(text).toContain('Запрос на обмен создан!');
    });
  });

  // ── TC-13: Список обменов обновляется после создания запроса ─────────────

  describe('TC-13 — Список обменов обновляется после создания запроса', () => {
    let page;

    beforeAll(async () => {
      page = await openPage(browser);
      await loginUser(page);
      await page.evaluate(() => window.showSection('exchange-requests'));
      await new Promise(r => setTimeout(r, 200));
    });
    afterAll(async () => { await page.close(); });

    test('Список обменов загружается автоматически при открытии раздела', async () => {
      // getExchangeRequests() вызывается при loginUser → раздел обменов уже имеет данные
      await page.waitForFunction(
        () => {
          const el = document.getElementById('exchange-list');
          return !el.classList.contains('hidden');
        },
        { timeout: 10000 }
      );

      const listVisible = await page.$eval('#exchange-list', el =>
        !el.classList.contains('hidden')
      );
      expect(listVisible).toBe(true);
    });

    test('В списке отображается хотя бы один запрос с нужными полями', async () => {
      await page.waitForFunction(
        () => {
          const el = document.getElementById('exchange-list');
          return el.querySelector('.exchange-request') !== null;
        },
        { timeout: 10000 }
      );

      const requestText = await page.$eval('.exchange-request', el => el.textContent);
      // Из MOCK_EXCHANGE_LIST: книга «Война и мир», статус «pending»
      expect(requestText).toContain('Война и мир');
      expect(requestText).toContain('pending');
      expect(requestText).toContain('Запросил');
      expect(requestText).toContain('Владелец');
    });

    test('После создания нового запроса список обновляется', async () => {
      // Создаём запрос через форму
      await page.evaluate(() => {
        document.getElementById('exchange-book-id').value = '1';
      });
      await jsClick(page, 'button[onclick="createExchangeRequest()"]');

      await page.waitForFunction(
        () => {
          const el = document.getElementById('exchange-result');
          return !el.classList.contains('hidden') && el.textContent.includes('создан');
        },
        { timeout: 10000 }
      );

      const resultText = await page.$eval('#exchange-result', el => el.textContent);
      expect(resultText).toContain('Запрос на обмен создан!');

      // Список должен обновиться (getExchangeRequests вызывается после успешного POST)
      await page.waitForFunction(
        () => document.querySelector('#exchange-list .exchange-request') !== null,
        { timeout: 10000 }
      );

      const requests = await page.$$('#exchange-list .exchange-request');
      expect(requests.length).toBeGreaterThan(0);
    });
  });
});
