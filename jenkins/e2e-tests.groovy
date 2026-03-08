pipeline {
    agent any

    triggers {
        cron('0 3 * * *')
    }

    environment {
        // Говорим Puppeteer использовать системный Chromium из Dockerfile
        PUPPETEER_SKIP_CHROMIUM_DOWNLOAD = 'true'
        PUPPETEER_EXECUTABLE_PATH        = '/usr/bin/chromium'
    }

    stages {

        stage('Start Docker services') {
            steps {
                sh '''
                    docker compose down -v || true
                    docker compose up -d --build
                    sleep 20
                '''
            }
        }

        stage('Setup Node.js') {
            steps {
                sh '''
                    cd frontend
                    npm ci
                '''
            }
        }

        stage('Run E2E tests') {
            steps {
                sh '''
                    cd frontend
                    npm test
                '''
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'frontend/junit.xml'
            sh 'docker compose down -v || true'
        }
        success {
            echo 'E2E тесты прошли успешно!'
        }
        failure {
            echo 'E2E тесты упали. Проверьте отчёт.'
        }
    }
}
