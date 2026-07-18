---
name: project-setup
user-invocable: true
description: 'Guides users through complete project setup and configuration. Covers environment setup, dependency management, build tools, CI/CD, and development tooling. Use when starting a new project, migrating existing code, or setting up development environments.'
argument-hint: '<project name, framework, or setup task>'
---

# Project Setup

Comprehensive project setup and configuration specialist for new projects, migrations, and development environment preparation.

## When to Use This Skill

- Starting a new project from scratch
- Setting up development environments
- Configuring build tools and CI/CD
- Managing dependencies across different environments
- Preparing projects for deployment
- Migrating existing projects to new structures

## Core Workflow

1. **Analyze requirements** - Determine project type, framework, and tooling needs
2. **Environment setup** - Configure development, testing, and production environments
3. **Dependency management** - Set up package managers and version control
4. **Build configuration** - Configure build tools and packaging
5. **Testing setup** - Configure test frameworks and CI/CD
6. **Validation** - Verify setup works across environments
7. **Documentation** - Create setup documentation and README

## Reference Guide

Load detailed guidance based on context:

| Topic | Reference | Load When |
|-------|-----------|-----------|
| Environment Setup | [references/environment-setup.md](./references/environment-setup.md) | Setting up dev/test/prod environments |
| Dependency Management | [references/dependency-management.md](./references/dependency-management.md) | Package managers, version control |
| Build Configuration | [references/build-configuration.md](./references/build-configuration.md) | Build tools, packaging, optimization |
| Testing Setup | [references/testing-setup.md](./references/testing-setup.md) | Test frameworks, CI/CD integration |
| Development Tools | [references/development-tools.md](./references/development-tools.md) | IDE plugins, linters, formatters |

## Constraints

### MUST DO

- Detect project type and framework
- Set up environment-specific configurations
- Configure version control with appropriate conventions
- Set up automated testing and CI/CD
- Document all setup steps
- Validate setup across environments

### MUST NOT DO

- Skip environment separation (dev/test/prod)
- Use hardcoded paths or credentials
- Assume single environment setup
- Skip version control configuration
- Create monolithic configuration files
- Skip validation steps

## Output Templates

When implementing project setup, provide:

1. Environment configuration files
2. Dependency management setup
3. Build configuration
4. Testing setup
5. CI/CD pipeline configuration
6. Documentation and README

## Knowledge Reference

Node.js, Python, Java, .NET, Docker, Kubernetes, CI/CD, Git, GitHub Actions, GitLab CI, Azure DevOps, Docker Compose, environment variables, configuration management, build tools, testing frameworks, IDE integration

## Documentation

https://jeffallan.github.io/claude-skills/skills/project-setup/
