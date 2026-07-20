import { expect, type Page, type Route, test } from '@playwright/test'

const ok = (data: unknown, message = 'success') => ({ code: 0, message, data })

const teacherUser = {
  id: 1,
  username: 'teacher_e2e',
  email: 'teacher@example.com',
  nickname: '端到端教师',
  status: 'active',
  roles: ['teacher'],
}

const adminUser = {
  ...teacherUser,
  id: 2,
  username: 'admin_e2e',
  nickname: '端到端管理员',
  roles: ['admin'],
}

async function authenticate(page: Page, user: typeof teacherUser) {
  await page.addInitScript((currentUser) => {
    localStorage.setItem('access_token', 'e2e-access-token')
    localStorage.setItem('refresh_token', 'e2e-refresh-token')
    localStorage.setItem('user', JSON.stringify(currentUser))
  }, user)
}

async function fulfillJson(route: Route, data: unknown) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) })
}

test('受保护路由会跳转登录并返回原教师页面', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '')
    if (path === '/auth/login') {
      expect(route.request().postDataJSON()).toEqual({
        account: 'teacher_e2e',
        password: 'Teacher123',
      })
      return fulfillJson(
        route,
        ok({
          access_token: 'e2e-access-token',
          refresh_token: 'e2e-refresh-token',
          expires_in: 1800,
          user: teacherUser,
        }),
      )
    }
    if (path === '/teacher/courses' || path === '/course-categories') {
      return fulfillJson(route, ok([]))
    }
    if (path === '/notifications/unread-count') {
      return fulfillJson(route, ok({ count: 0 }))
    }
    return fulfillJson(route, ok([]))
  })

  await page.goto('/app/teacher')
  await expect(page).toHaveURL(/\/login\?redirect=/)
  await page.locator('input').nth(0).fill('teacher_e2e')
  await page.locator('input').nth(1).fill('Teacher123')
  await page.getByRole('button', { name: '进入 EduFlow' }).click()
  await expect(page).toHaveURL(/\/app\/teacher$/)
  await expect(page.getByRole('heading', { name: '教师工作台' })).toBeVisible()
})

test('教师可以在题库界面创建题目', async ({ page }) => {
  await authenticate(page, teacherUser)
  const questions: any[] = []
  let submitted: any
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname.replace('/api/v1', '')
    if (path === '/notifications/unread-count') return fulfillJson(route, ok({ count: 0 }))
    if (path === '/teacher/courses') return fulfillJson(route, ok([]))
    if (path === '/course-categories' || path === '/papers') return fulfillJson(route, ok([]))
    if (path === '/questions' && request.method() === 'GET') {
      return fulfillJson(route, ok(questions))
    }
    if (path === '/questions' && request.method() === 'POST') {
      submitted = request.postDataJSON()
      questions.push({ id: 11, ...submitted })
      return fulfillJson(route, ok(questions[0]))
    }
    return fulfillJson(route, ok([]))
  })

  await page.goto('/app/teacher')
  await page.getByRole('tab', { name: '题库管理' }).click()
  await page.getByRole('button', { name: '新增题目' }).click()
  const dialog = page.getByRole('dialog', { name: '新增题目' })
  await dialog.locator('textarea').first().fill('FastAPI 使用什么进行数据校验？')
  await dialog.locator('.el-form-item').filter({ hasText: '选项 A' }).locator('input').fill('Pydantic')
  await dialog.locator('.el-form-item').filter({ hasText: '选项 B' }).locator('input').fill('Jinja2')
  await dialog.getByRole('button', { name: '保存题目' }).click()

  await expect(page.getByText('FastAPI 使用什么进行数据校验？')).toBeVisible()
  expect(submitted).toMatchObject({
    question_type: 'single',
    correct_answers: ['A'],
    options: { A: 'Pydantic', B: 'Jinja2' },
  })
})

test('管理员可以审核课程并分配用户角色', async ({ page }) => {
  await authenticate(page, adminUser)
  const course = {
    id: 21,
    title: '待审核 Python 课程',
    subtitle: '',
    description: '完整课程内容',
    category_id: 1,
    teacher_id: 8,
    status: 'pending_review',
    difficulty: 'beginner',
    total_duration: 600,
    student_count: 0,
    chapters: [
      {
        id: 31,
        title: '第一章',
        sort_order: 1,
        lessons: [
          {
            id: 41,
            title: '第一课',
            lesson_type: 'video',
            content: '',
            duration_seconds: 600,
            sort_order: 1,
            is_required: true,
            is_free_preview: false,
          },
        ],
      },
    ],
  }
  let pendingCourses = [course]
  let auditPayload: any
  let rolePayload: any
  const permission = { id: 1, name: '创建课程', code: 'course:create', description: '' }
  const roles = [
    { id: 1, name: '管理员', code: 'admin', description: '', is_system: true, permissions: [] },
    { id: 2, name: '教师', code: 'teacher', description: '', is_system: true, permissions: [permission] },
  ]
  const users: any[] = [
    {
      id: 9,
      username: 'new_teacher',
      email: 'new@example.com',
      nickname: '新教师',
      status: 'active',
      roles: [],
      created_at: '2026-07-20T00:00:00Z',
    },
  ]

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname.replace('/api/v1', '')
    if (path === '/notifications/unread-count') return fulfillJson(route, ok({ count: 0 }))
    if (path === '/statistics/admin/overview') {
      return fulfillJson(
        route,
        ok({ user_total: 12, active_users: 11, course_total: 4, published_courses: 3, exam_total: 2, learning_seconds: 7200 }),
      )
    }
    if (path === '/admin/courses') {
      return fulfillJson(route, ok({ items: pendingCourses, page: 1, page_size: 10, total: pendingCourses.length, pages: 1 }))
    }
    if (path === '/courses/21/audit') {
      auditPayload = request.postDataJSON()
      pendingCourses = []
      return fulfillJson(route, ok({ ...course, status: auditPayload.approved ? 'published' : 'rejected' }))
    }
    if (path === '/users' && request.method() === 'GET') return fulfillJson(route, ok(users))
    if (path === '/roles') return fulfillJson(route, ok(roles))
    if (path === '/permissions') return fulfillJson(route, ok([permission]))
    if (path === '/operation-logs') {
      return fulfillJson(route, ok({ items: [], page: 1, page_size: 20, total: 0, pages: 0 }))
    }
    if (path === '/users/9/roles') {
      rolePayload = request.postDataJSON()
      users[0].roles = roles.filter((role) => rolePayload.ids.includes(role.id))
      return fulfillJson(route, ok(users[0]))
    }
    return fulfillJson(route, ok([]))
  })

  await page.goto('/app/admin')
  await expect(page.getByRole('heading', { name: '管理中心' })).toBeVisible()
  await page.getByRole('tab', { name: '课程审核' }).click()
  await page.getByRole('button', { name: '开始审核' }).click()
  const auditDialog = page.getByRole('dialog', { name: '审核课程' })
  await auditDialog.getByText('驳回修改').click()
  await auditDialog.locator('textarea').fill('请补充课程练习。')
  await auditDialog.getByRole('button', { name: '确认审核' }).click()
  await expect(page.getByText('暂无符合条件的课程')).toBeVisible()
  expect(auditPayload).toEqual({ approved: false, opinion: '请补充课程练习。' })

  await page.getByRole('tab', { name: '用户与角色' }).click()
  await page.getByRole('button', { name: '分配角色' }).click()
  const roleDialog = page.getByRole('dialog', { name: '为 new_teacher 分配角色' })
  await roleDialog.getByText('教师', { exact: true }).click()
  await roleDialog.getByRole('button', { name: '保存角色' }).click()
  expect(rolePayload).toEqual({ ids: [2] })
})
