pipeline {
    agent {
        node {
            label 'docker'
        }
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 30, unit: 'MINUTES')
        skipStagesAfterUnstable()
        parallelsAlwaysFailFast()
        disableConcurrentBuilds()
    }

    environment {
        // Registry and Infrastructure Configuration
        REGISTRY_URL = "icr.io/etl-registry"
        REGION = "us-south"
        CLUSTER_NAME = "etl-cluster"
        RESOURCE_GROUP = "ETL-rg"

        // Build Configuration
        IMAGE_TAG = "${env.BUILD_NUMBER}-${env.GIT_COMMIT?.take(7) ?: 'unknown'}"
        BUILD_TIMESTAMP = sh(script: 'date +%Y%m%d-%H%M%S', returnStdout: true).trim()

        // Branch-specific Configuration
        TARGET_NAMESPACE = getTargetNamespace()
        IS_PRODUCTION = "${env.BRANCH_NAME == 'master' ? 'true' : 'false'}"
        IS_DEPLOY_BRANCH = isDeployableBranch()

        // Service Configuration
        SERVICES = "extract,transform,load,scheduler,visualization"
    }

    stages {
        stage('Initialize') {
            steps {
                script {
                    // Display build information
                    echo """
                    ╔═══════════════════════════════════════════════════════════════╗
                    ║                    PSX ETL Pipeline Build                     ║
                    ╠═══════════════════════════════════════════════════════════════╣
                    ║ Branch:           ${env.BRANCH_NAME}
                    ║ Target Namespace: ${env.TARGET_NAMESPACE}
                    ║ Image Tag:        ${env.IMAGE_TAG}
                    ║ Build Number:     ${env.BUILD_NUMBER}
                    ║ Commit:           ${env.GIT_COMMIT?.take(7) ?: 'N/A'}
                    ║ Is Production:    ${env.IS_PRODUCTION}
                    ║ Timestamp:        ${env.BUILD_TIMESTAMP}
                    ╚═══════════════════════════════════════════════════════════════╝
                    """

                    // Validate branch
                    if (env.IS_DEPLOY_BRANCH == 'false') {
                        currentBuild.result = 'NOT_BUILT'
                        echo "⚠️  Branch '${env.BRANCH_NAME}' is not configured for deployment. Skipping pipeline."
                        return
                    }

                    // Set build description
                    currentBuild.description = "Branch: ${env.BRANCH_NAME} | Namespace: ${env.TARGET_NAMESPACE}"
                    currentBuild.displayName = "#${env.BUILD_NUMBER}-${env.BRANCH_NAME}"
                }
            }
        }

        stage('Checkout & Validation') {
            when {
                expression { env.IS_DEPLOY_BRANCH == 'true' }
            }
            steps {
                script {
                    // Clean workspace
                    cleanWs()

                    // Checkout source code
                    checkout scm

                    // Validate required files exist
                    def requiredPaths = [
                        './psx-etl/services/extract/Dockerfile',
                        './psx-etl/services/transform/Dockerfile',
                        './psx-etl/services/load/Dockerfile',
                        './psx-etl/services/scheduler/Dockerfile',
                        './psx-etl/services/visualization/Dockerfile',
                        './psx-etl/infra/k8s/services/',
                        './psx-etl/infra/k8s/database/'
                    ]

                    requiredPaths.each { path ->
                        if (!fileExists(path)) {
                            error "❌ Required path not found: ${path}"
                        }
                    }

                    echo "✅ All required files validated successfully"
                }
            }
        }

        stage('Unit Tests') {
            when {
                expression { env.IS_DEPLOY_BRANCH == 'true' }
            }
            steps {
                script {
                    // The tests run offline (in-memory SQLite, mocked HTTP), so no database or network is needed.
                    docker.image('python:3.9-slim').inside('-e HOME=/tmp') {
                        dir('psx-etl') {
                            sh '''
                                pip install --user --no-cache-dir -r requirements.txt
                                python -m pytest tests -q
                            '''
                        }
                    }
                }
            }
        }

        stage('IBM Cloud Authentication') {
            when {
                expression { env.IS_DEPLOY_BRANCH == 'true' }
            }
            steps {
                script {
                    withCredentials([string(credentialsId: 'ibm-cloud-api-key', variable: 'IBM_CLOUD_API_KEY')]) {
                        try {
                            sh '''
                                echo "🔐 Authenticating with IBM Cloud..."

                                # Login to IBM Cloud
                                ibmcloud login --apikey $IBM_CLOUD_API_KEY -r $REGION --quiet

                                # Target resource group
                                ibmcloud target -g $RESOURCE_GROUP --quiet

                                # Login to Container Registry
                                ibmcloud cr login

                                # Configure kubectl for cluster
                                ibmcloud ks cluster config --cluster $CLUSTER_NAME

                                # Verify cluster connection
                                kubectl cluster-info --request-timeout=10s

                                echo "✅ IBM Cloud authentication successful"
                            '''
                        } catch (Exception e) {
                            error "❌ IBM Cloud authentication failed: ${e.getMessage()}"
                        }
                    }
                }
            }
        }

        stage('Build & Push Container Images') {
            when {
                expression { env.IS_DEPLOY_BRANCH == 'true' }
            }
            steps {
                script {
                    def services = env.SERVICES.split(',')
                    def parallelBuilds = [:]

                    services.each { service ->
                        parallelBuilds[service.capitalize()] = {
                            node('docker') {
                                try {
                                    echo "🏗️  Building ${service} service..."

                                    checkout scm

                                    def imageName = "${env.REGISTRY_URL}/psx-etl-${service}:${env.IMAGE_TAG}"
                                    def serviceDir = "./psx-etl/services/${service}"

                                    // Verify Dockerfile exists
                                    if (!fileExists("${serviceDir}/Dockerfile")) {
                                        error "❌ Dockerfile not found for service: ${service}"
                                    }

                                    // Build and push image
                                    def image = docker.build(imageName, serviceDir)
                                    image.push()
                                    image.push("${service}-latest")  // Also tag as latest

                                    echo "✅ Successfully built and pushed: ${imageName}"

                                } catch (Exception e) {
                                    error "❌ Failed to build ${service}: ${e.getMessage()}"
                                } finally {
                                    // Clean up Docker images on node
                                    sh "docker system prune -f --filter until=24h || true"
                                }
                            }
                        }
                    }

                    // Execute parallel builds
                    parallel parallelBuilds
                    echo "✅ All container images built and pushed successfully"
                }
            }
        }

        stage('Security Scan') {
            when {
                expression { env.IS_DEPLOY_BRANCH == 'true' }
            }
            steps {
                script {
                    if (env.IS_PRODUCTION == 'true') {
                        echo "🔍 Running security scan for production deployment..."
                        // Add your security scanning tools here
                        // Example: Trivy, Snyk, or IBM Cloud Security Advisor
                        sh '''
                            echo "Running Trivy Security Scan..."
                            trivy image --severity HIGH,CRITICAL --no-progress ${REGISTRY_URL}/psx-etl-extract:${IMAGE_TAG}
                            trivy image --severity HIGH,CRITICAL --no-progress ${REGISTRY_URL}/psx-etl-transform:${IMAGE_TAG}
                            trivy image --severity HIGH,CRITICAL --no-progress ${REGISTRY_URL}/psx-etl-load:${IMAGE_TAG}
                            trivy image --severity HIGH,CRITICAL --no-progress ${REGISTRY_URL}/psx-etl-visualization:${IMAGE_TAG}
                            trivy image --severity HIGH,CRITICAL --no-progress ${REGISTRY_URL}/psx-etl-scheduler:${IMAGE_TAG}
                        '''
                    } else {
                        echo "ℹ️  Skipping security scan for non-production deployment"
                    }
                }
            }
        }

        stage('Production Deployment Approval') {
            when {
                expression { env.IS_PRODUCTION == 'true' }
            }
            steps {
                script {
                    try {
                        echo "⏳ Requesting production deployment approval..."

                        def approvalMessage = """
                        🚀 Production Deployment Request

                        Branch: ${env.BRANCH_NAME}
                        Build: ${env.BUILD_NUMBER}
                        Commit: ${env.GIT_COMMIT?.take(7)}
                        Image Tag: ${env.IMAGE_TAG}
                        Timestamp: ${env.BUILD_TIMESTAMP}

                        Services to deploy: ${env.SERVICES.replace(',', ', ')}
                        Target Namespace: ${env.TARGET_NAMESPACE}
                        """

                        timeout(time: 15, unit: 'MINUTES') {
                            def approval = input(
                                message: approvalMessage,
                                ok: '🚀 Deploy to Production',
                                parameters: [
                                    choice(
                                        name: 'DEPLOYMENT_TYPE',
                                        choices: ['rolling-update', 'blue-green'],
                                        description: 'Select deployment strategy'
                                    ),
                                    booleanParam(
                                        name: 'RUN_SMOKE_TESTS',
                                        defaultValue: true,
                                        description: 'Run smoke tests after deployment'
                                    )
                                ],
                                submitterParameter: 'APPROVER'
                            )

                            env.DEPLOYMENT_TYPE = approval.DEPLOYMENT_TYPE
                            env.RUN_SMOKE_TESTS = approval.RUN_SMOKE_TESTS.toString()

                            echo "✅ Production deployment approved by: ${env.APPROVER}"
                            echo "📋 Deployment type: ${env.DEPLOYMENT_TYPE}"
                        }

                    } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException e) {
                        echo "❌ Production deployment approval timeout or cancelled"
                        currentBuild.result = 'ABORTED'
                        error "Production deployment cancelled - no approval received"
                    }
                }
            }
        }

        stage('Pre-deployment Checks') {
            when {
                expression { env.IS_DEPLOY_BRANCH == 'true' }
            }
            steps {
                script {
                    echo "🔍 Running pre-deployment checks..."

                    sh '''
                        # Verify namespace exists
                        kubectl get namespace ${TARGET_NAMESPACE} || kubectl create namespace ${TARGET_NAMESPACE}

                        # Verify database namespace exists
                        kubectl get namespace database || kubectl create namespace database

                        # Check cluster resources
                        kubectl top nodes --no-headers | head -5 || echo "Node metrics not available"

                        # Verify registry connectivity
                        ibmcloud cr image-list --restrict ${REGISTRY_URL} --no-trunc | head -n 2 > /dev/null

                        echo "✅ Pre-deployment checks completed"
                    '''
                }
            }
        }

        stage('Deploy to Kubernetes') {
            when {
                expression { env.IS_DEPLOY_BRANCH == 'true' }
            }
            steps {
                script {
                    try {
                        echo "🚀 Starting deployment to ${env.TARGET_NAMESPACE} namespace..."

                        sh '''
                            # Create backup of current deployment (production only)
                            if [ "${IS_PRODUCTION}" = "true" ]; then
                                echo "📦 Creating backup of current production deployment..."
                                kubectl get deployments -n ${TARGET_NAMESPACE} -o yaml > deployment-backup-${BUILD_NUMBER}.yaml || echo "No existing deployments to backup"
                            fi

                            # Deploy database components (shared across environments)
                            echo "🗄️  Deploying database components..."
                            kubectl apply --namespace=database -R -f psx-etl/infra/k8s/database/ --record

                            # Deploy application services
                            echo "📦 Deploying application services to ${TARGET_NAMESPACE}..."
                            kubectl apply -n ${TARGET_NAMESPACE} -R -f psx-etl/infra/k8s/services/ --record

                            # Apply specific built image tags securely using Kubernetes set image
                            echo "🔄 Rolling out pipeline with newly built images..."
                            kubectl set image deployment/extract-deployment extract=icr.io/etl-registry/psx-etl-extract:${IMAGE_TAG} -n ${TARGET_NAMESPACE}
                            kubectl set image deployment/transform-deployment transform=icr.io/etl-registry/psx-etl-transform:${IMAGE_TAG} -n ${TARGET_NAMESPACE}
                            kubectl set image deployment/load-deployment load=icr.io/etl-registry/psx-etl-load:${IMAGE_TAG} -n ${TARGET_NAMESPACE}
                            kubectl set image deployment/visualization-deployment visualization=icr.io/etl-registry/psx-etl-visualization:${IMAGE_TAG} -n ${TARGET_NAMESPACE}
                            kubectl set image deployment/scheduler-deployment scheduler=icr.io/etl-registry/psx-etl-scheduler:${IMAGE_TAG} -n ${TARGET_NAMESPACE}

                            # Deploy ingress configuration dynamically
                            echo "🌐 Deploying ingress configuration..."
                            sed "s|namespace: dev|namespace: ${TARGET_NAMESPACE}|g" psx-etl/infra/k8s/ingress.yaml | kubectl apply -n ${TARGET_NAMESPACE} -f -

                            # Wait for deployments to be ready
                            echo "⏳ Waiting for deployments to be ready..."
                            kubectl wait --for=condition=available --timeout=300s deployment --all -n ${TARGET_NAMESPACE}

                            # Display deployment status
                            echo "📊 Deployment status:"
                            kubectl get pods,services,ingress -n ${TARGET_NAMESPACE}
                        '''

                        echo "✅ Deployment to ${env.TARGET_NAMESPACE} completed successfully!"

                    } catch (Exception e) {
                        echo "❌ Deployment failed: ${e.getMessage()}"

                        // Rollback for production failures
                        if (env.IS_PRODUCTION == 'true') {
                            echo "🔄 Initiating rollback for production..."
                            sh '''
                                if [ -f "deployment-backup-${BUILD_NUMBER}.yaml" ]; then
                                    echo "📦 Rolling back to previous deployment..."
                                    kubectl apply -f deployment-backup-${BUILD_NUMBER}.yaml
                                else
                                    echo "⚠️  No backup found, manual intervention may be required"
                                fi
                            '''
                        }

                        throw e
                    }
                }
            }
        }

        stage('Post-deployment Validation') {
            when {
                expression { env.IS_DEPLOY_BRANCH == 'true' }
            }
            steps {
                script {
                    echo "🧪 Running post-deployment validation..."

                    sh '''
                        # Health check for all services
                        echo "🏥 Checking service health..."

                        # Wait a bit for services to stabilize
                        sleep 30

                        # Check pod status
                        FAILED_PODS=$(kubectl get pods -n ${TARGET_NAMESPACE} --field-selector=status.phase!=Running --no-headers | wc -l)

                        if [ $FAILED_PODS -gt 0 ]; then
                            echo "❌ Found ${FAILED_PODS} failed pods:"
                            kubectl get pods -n ${TARGET_NAMESPACE} --field-selector=status.phase!=Running
                            kubectl describe pods -n ${TARGET_NAMESPACE} --field-selector=status.phase!=Running
                            exit 1
                        fi

                        echo "✅ All pods are running successfully"

                        # Display final status
                        kubectl get all -n ${TARGET_NAMESPACE}
                    '''

                    // Run smoke tests for production
                    if (env.IS_PRODUCTION == 'true' && env.RUN_SMOKE_TESTS == 'true') {
                        echo "🧪 Running production smoke tests..."
                        sh '''
                            # Ask every service for /health from inside its own pod. The images are python:3.9-slim,
                            # so python is always there (the scheduler image has no curl). A non-200 answer fails the build.
                            for svc in extract:8000 transform:8001 load:8003 scheduler:8004 visualization:8002; do
                                name=${svc%%:*}
                                port=${svc##*:}
                                echo "Checking ${name} on port ${port}..."
                                kubectl exec -n ${TARGET_NAMESPACE} deploy/${name}-deployment -- python -c "import sys, urllib.request as u; sys.exit(u.urlopen('http://localhost:${port}/health', timeout=10).status != 200)" || { echo "❌ ${name} /health check failed"; exit 1; }
                            done

                            echo "✅ All services answered /health with 200"
                        '''
                    }

                    echo "✅ Post-deployment validation completed successfully"
                }
            }
        }
    }

    post {
        always {
            script {
                // Archive important files
                if (env.IS_DEPLOY_BRANCH == 'true') {
                    archiveArtifacts artifacts: 'deployment-backup-*.yaml', allowEmptyArchive: true
                }

                echo "🧹 Cleaning up workspace..."
                cleanWs()
            }
        }

        success {
            script {
                if (env.IS_DEPLOY_BRANCH == 'true') {
                    def successMessage = """
                    ✅ **PSX ETL Deployment Successful**

                    📋 **Details:**
                    • Branch: `${env.BRANCH_NAME}`
                    • Namespace: `${env.TARGET_NAMESPACE}`
                    • Build: `${env.BUILD_NUMBER}`
                    • Image Tag: `${env.IMAGE_TAG}`
                    • Commit: `${env.GIT_COMMIT?.take(7)}`
                    • Duration: ${currentBuild.durationString}

                    ${
                        env.IS_PRODUCTION == 'true'
                            ? '🚀 **Production deployment completed!**'
                            : '🔧 **Development deployment completed!**'
                    }
                    """

                    echo successMessage

                    // Add Slack/Teams notification here if needed
                    // slackSend(message: successMessage, color: 'good')
                }
            }
        }

        failure {
            script {
                if (env.IS_DEPLOY_BRANCH == 'true') {
                    def failureMessage = """
                    ❌ **PSX ETL Deployment Failed**

                    📋 **Details:**
                    • Branch: `${env.BRANCH_NAME}`
                    • Namespace: `${env.TARGET_NAMESPACE}`
                    • Build: `${env.BUILD_NUMBER}`
                    • Failed Stage: `${env.STAGE_NAME ?: 'Unknown'}`
                    • Duration: ${currentBuild.durationString}

                    🔗 **Build URL:** ${env.BUILD_URL}
                    """

                    echo failureMessage

                    // Add alerting here if needed
                    // slackSend(message: failureMessage, color: 'danger')
                }
            }
        }

        aborted {
            script {
                echo "⏹️  **Pipeline Aborted** - Branch: ${env.BRANCH_NAME}, Build: ${env.BUILD_NUMBER}"
            }
        }

        unstable {
            script {
                echo "⚠️  **Pipeline Unstable** - Branch: ${env.BRANCH_NAME}, Build: ${env.BUILD_NUMBER}"
            }
        }
    }
}

// Helper Functions
def getTargetNamespace() {
    switch (env.BRANCH_NAME) {
        case 'master':
            return 'prod'
        case 'dev':
        case 'qa-test':
            return 'dev'
        default:
            return 'dev'  // Default fallback
    }
}

def isDeployableBranch() {
    def allowedBranches = ['dev', 'qa-test', 'master']
    return allowedBranches.contains(env.BRANCH_NAME) ? 'true' : 'false'
}
