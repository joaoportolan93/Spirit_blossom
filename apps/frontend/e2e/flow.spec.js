import { test, expect } from "@playwright/test";

test.describe("Fluxo E2E: cadastro → post → seguir → ver", () => {
  const timestamp = Date.now();
  const user1 = {
    username: `autor${timestamp}`,
    email: `autor${timestamp}@example.com`,
    password: "Password123!",
    birthDate: "2000-01-01",
  };
  const user2 = {
    username: `seguidor${timestamp}`,
    email: `seguidor${timestamp}@example.com`,
    password: "Password123!",
    birthDate: "2002-05-15",
  };
  const postContent = `Publicação de teste E2E do autor ${timestamp}`;

  test("1. Cadastro autor, criação de post, cadastro seguidor, follow e visualização no feed", async ({
    page,
  }) => {
    // 1. Cadastrar usuário 1 (Autor)
    await page.goto("/register");
    await page.fill('[data-testid="register-email"]', user1.email);
    await page.fill('[data-testid="register-username"]', user1.username);
    await page.fill('[data-testid="register-birth-date"]', user1.birthDate);
    await page.fill('[data-testid="register-password"]', user1.password);
    await page.fill('[data-testid="register-password-confirm"]', user1.password);
    await page.check('[data-testid="register-terms"]');
    await page.click('[data-testid="register-submit"]');

    // Aguarda redirecionamento para o feed
    await expect(page).toHaveURL("/");

    // 2. Criar uma publicação no feed (abre modal + Novo Post)
    await page.click('[data-testid="feed-new-post-btn"]');
    await page.fill('[data-testid="composer-textarea"]', postContent);
    await page.click('[data-testid="publish-button"]');

    // Confirma que a publicação apareceu na tela
    await expect(page.locator(`text=${postContent}`)).toBeVisible();

    // 3. Fazer logout do Autor
    await page.click('button:has-text("Sair"), button:has-text("Log out")');
    await expect(page).toHaveURL("/login");

    // 4. Cadastrar usuário 2 (Seguidor)
    await page.goto("/register");
    await page.fill('[data-testid="register-email"]', user2.email);
    await page.fill('[data-testid="register-username"]', user2.username);
    await page.fill('[data-testid="register-birth-date"]', user2.birthDate);
    await page.fill('[data-testid="register-password"]', user2.password);
    await page.fill('[data-testid="register-password-confirm"]', user2.password);
    await page.check('[data-testid="register-terms"]');
    await page.click('[data-testid="register-submit"]');

    await expect(page).toHaveURL("/");

    // 5. Acessar perfil do usuário 1 e seguir
    await page.goto(`/profile/${user1.username}`);
    const followBtn = page.locator('[data-testid="follow-button"]');
    await expect(followBtn).toBeVisible();
    await followBtn.click();
    await expect(followBtn).toHaveText(/Deixar de seguir|Unfollow/);

    // 6. Voltar ao feed e conferir a publicação do seguido
    await page.goto("/");
    await expect(page.locator(`text=${postContent}`)).toBeVisible();
  });
});

