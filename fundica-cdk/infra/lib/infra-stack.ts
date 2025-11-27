import * as dotenv from 'dotenv';
import * as path from 'path';
import * as cdk from 'aws-cdk-lib/core';
import { Construct } from 'constructs';
import * as aws_s3 from 'aws-cdk-lib/aws-s3';
import * as aws_s3_deployment from 'aws-cdk-lib/aws-s3-deployment';
import * as aws_lambda from 'aws-cdk-lib/aws-lambda';
import * as aws_iam from 'aws-cdk-lib/aws-iam';
import * as aws_sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as aws_ecr_assets from 'aws-cdk-lib/aws-ecr-assets';
import * as aws_sfn_tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
dotenv.config();

export class InfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    //=======================================
    // S3 BUCKETS
    //=======================================

    const s3_docs = new aws_s3.Bucket(this, 'DocsBucket', {
      bucketName: `fundica-docs-${this.account}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true
    })

    new aws_s3_deployment.BucketDeployment(this, 'DeployPrompts', {
      sources: [
        aws_s3_deployment.Source.asset(path.join(__dirname, "../../local-files"))
      ],
      destinationBucket: s3_docs
    })

    const s3_filled = new aws_s3.Bucket(this, 'FilledApplicationBucket', {
      bucketName: `fundica-filled-${this.account}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true
    })

    const s3_users = new aws_s3.Bucket(this, 'UserBucket', {
      bucketName: `fundica-users-${this.account}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true
    })

    //=======================================
    // IAM ROLES AND POLICIES
    //=======================================

    // Bedrock policy---------------------
    const bedrock_policy = new aws_iam.Policy(this, 'KBPolicy', {
      statements: [
        new aws_iam.PolicyStatement({
          actions: [
            'bedrock:*'
          ],
          resources: ['*'],
          effect: aws_iam.Effect.ALLOW
        })
      ]
    })

    // Lambda role of KB sync lambda---------
    const kb_lambda_role = new aws_iam.Role(this, 'KBRole', {
      assumedBy: new aws_iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        aws_iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ]
    })

    // Attaching policy to role
    bedrock_policy.attachToRole(kb_lambda_role)

    // Lambda role for Application form completion lambda-----
    const application_role = new aws_iam.Role(this, 'ApplicationRole', {
      assumedBy: new aws_iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        aws_iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ]
    })

    // Attaching policy to role
    bedrock_policy.attachToRole(application_role)

    //=======================================
    // LAMBDA FUNCTIONS
    //=======================================

    // Function to create metadata when S3 gets populated
    const metadata_creation_lambda = new aws_lambda.Function(this, 'MetadataCreationLambda', {
      functionName: 'metadata-creation-lambda',
      description: 'Lambda that creates metadata for files that have been uploaded to S3',
      code: aws_lambda.Code.fromAsset(path.join(__dirname, "../../services/lambdas")),
      handler: 'metadata_creation_lambda.lambda_handler',
      runtime: aws_lambda.Runtime.PYTHON_3_13,
      timeout: cdk.Duration.minutes(15),
      memorySize: 1024,
      ephemeralStorageSize: cdk.Size.mebibytes(1024),
      environment: {
        S3_USERS: s3_users.bucketName 
      }
    })

    // Grant Metadata creation lambda with Read and Write permissions to S3
    s3_users.grantReadWrite(metadata_creation_lambda);

    // Knowledge base sync lambda
    const kb_sync_lambda = new aws_lambda.Function(this, 'KBSyncLambda', {
      functionName: 'kb-sync-lambda',
      description: 'Lamda that will run a sync job after all the files and their metadata have been uploaded',
      code: aws_lambda.Code.fromAsset(path.join(__dirname, '../../services/lambdas/')),
      handler: 'kb_sync_lambda.lambda_handler',
      runtime: aws_lambda.Runtime.PYTHON_3_13,
      timeout: cdk.Duration.minutes(15),
      memorySize: 512,
      role: kb_lambda_role,
      environment: {
        KB_ID: process.env.KB_ID || '',
        KB_DATASOURCE_ID: process.env.KB_DATASOURCE_ID || ''
      }
    })

    // Application form completion lambda
    // const application_form_lambda = new aws_lambda.Function(this, 'ApplicationFormLambda', {
    //   functionName: 'application-form-completion-lambda',
    //   description: 'Lamda that will complete the appplication form',
    //   code: aws_lambda.Code.fromAsset(path.join(__dirname, '../../services/lambdas/')),
    //   handler: 'application_completion_lambda.lambda_handler',
    //   runtime: aws_lambda.Runtime.PYTHON_3_13,
    //   timeout: cdk.Duration.minutes(15),
    //   memorySize: 2048,
    //   role: application_role,
    //   environment: {
    //     S3_DOCS: s3_docs.bucketName,
    //     KB_ID: process.env.KB_ID || '',
    //     KB_DATASOURCE_ID: process.env.KB_DATASOURCE_ID || ''
    //   }
    // })

    const application_form_lambda = new aws_lambda.DockerImageFunction(this, 'ApplicationFormLambda', {
      functionName: 'application-form-completion-lambda',
      description: 'Lamda that will complete the appplication form',
      code: aws_lambda.DockerImageCode.fromImageAsset(
        path.join(__dirname, '../../services/lambdas/application-completion-lambda/'), 
        {
          platform: aws_ecr_assets.Platform.LINUX_AMD64
        }
      ),
      timeout: cdk.Duration.minutes(15),
      memorySize: 2048,
      role: application_role,
      environment: {
        S3_DOCS: s3_docs.bucketName,
        S3_FILLED: s3_filled.bucketName,
        KB_ID: process.env.KB_ID || ''
      }
    })

    // Grant S3 access to application form completion lambda
    s3_filled.grantReadWrite(application_form_lambda)
    s3_docs.grantReadWrite(application_form_lambda)

    // MD to DOCX lambda
    const md_docx_lambda = new aws_lambda.DockerImageFunction(this, 'PyPandocLambda', {
      functionName: 'md-to-docx-lambda',
      code: aws_lambda.DockerImageCode.fromImageAsset(
        path.join(__dirname, '../../services/lambdas/pypandoc-lambda/'),
        {
          platform: aws_ecr_assets.Platform.LINUX_AMD64
        }
      ),
      timeout: cdk.Duration.minutes(15),
      memorySize: 1024,
      environment: {
        S3_FILLED: s3_filled.bucketName
      }
    })

    s3_filled.grantReadWrite(md_docx_lambda)

    //=======================================
    // STEPFUNCTIONS
    //=======================================

    const first_task_metadata = new aws_sfn_tasks.LambdaInvoke(this, 'InvokeMetadataLambda', {
      lambdaFunction: metadata_creation_lambda,
      outputPath: '$.Payload'
    })

    const second_task_kb = new aws_sfn_tasks.LambdaInvoke(this, 'InvokeKBSyncLambda', {
      lambdaFunction: kb_sync_lambda,
      outputPath: '$.Payload'
    })

    const third_task_application = new aws_sfn_tasks.LambdaInvoke(this, 'InvokeApplicationLambda', {
      lambdaFunction: application_form_lambda,
      outputPath: '$.Payload'
    })

    const fourth_task_md = new aws_sfn_tasks.LambdaInvoke(this, 'InvokeMdDocxLambda', {
      lambdaFunction: md_docx_lambda,
      outputPath: '$.Payload'
    })

    const definition = first_task_metadata
    .next(second_task_kb)
    .next(third_task_application)
    // .next(fourth_task_md)

    const stateMachine = new aws_sfn.StateMachine(this, 'StateMachine', {
      definitionBody: aws_sfn.DefinitionBody.fromChainable(definition),
      timeout: cdk.Duration.minutes(15),
      stateMachineName: 'form-completion-orchestration'
    })
  }
}
