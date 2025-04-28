import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as awsx from "@pulumi/awsx";
import * as path from "path";
import * as fs from "fs";

// Create an IAM role for the Lambdas
const lambdaRole = new aws.iam.Role("lambdaRole", {
    assumeRolePolicy: aws.iam.assumeRolePolicyForPrincipal({
        Service: "lambda.amazonaws.com",
    }),
});

new aws.iam.RolePolicyAttachment("lambdaRolePolicy", {
    role: lambdaRole.name,
    policyArn: aws.iam.ManagedPolicy.AWSLambdaBasicExecutionRole,
});

new aws.iam.RolePolicyAttachment("lambdaRoleLogsPolicy", {
    role: lambdaRole.name,
    policyArn: aws.iam.ManagedPolicy.CloudWatchLogsFullAccess,
});

// Define the first Lambda function
const lambda1 = new aws.lambda.Function("lambda1", {
    runtime: "python3.9",
    code: new pulumi.asset.AssetArchive({
        ".": new pulumi.asset.FileArchive(path.join(__dirname, "lambda1")),
    }),
    handler: "handler.lambda_handler",
    role: lambdaRole.arn,
});

// Define the second Lambda function
const lambda2 = new aws.lambda.Function("lambda2", {
    runtime: "python3.9",
    code: new pulumi.asset.AssetArchive({
        ".": new pulumi.asset.FileArchive(path.join(__dirname, "lambda2")),
    }),
    handler: "handler.lambda_handler",
    role: lambdaRole.arn,
});

// Define the third Lambda function
const lambda3 = new aws.lambda.Function("lambda3", {
    runtime: "python3.9",
    code: new pulumi.asset.AssetArchive({
        ".": new pulumi.asset.FileArchive(path.join(__dirname, "lambda3")),
    }),
    handler: "handler.lambda_handler",
    role: lambdaRole.arn,
});


// Create a Step Function
const stepFunctionRole = new aws.iam.Role("stepFunctionRole", {
    assumeRolePolicy: aws.iam.assumeRolePolicyForPrincipal({
        Service: "states.amazonaws.com",
    }),
});

new aws.iam.RolePolicyAttachment("stepFunctionPolicy", {
    role: stepFunctionRole.name,
    policyArn: aws.iam.ManagedPolicy.AWSLambdaRole,
});

//Attach a policy to allow the Step Function to write logs to the CloudWatch Log Group
new aws.iam.RolePolicyAttachment("stepFunctionLogsPolicy", {
    role: stepFunctionRole.name,
    policyArn: aws.iam.ManagedPolicy.CloudWatchLogsFullAccess,
});

//Create a CloudWatch Log Group for the Step Function
const stepFunctionLogs = new aws.cloudwatch.LogGroup("stepFunctionLogs");

//Update the Step Function definition to split and process in parallel
const stepFunction = new aws.sfn.StateMachine("stepFunction", {
    roleArn: stepFunctionRole.arn,
    definition: pulumi.interpolate`{
    "Comment": "A description of my state machine",
    "StartAt": "Lambda 1",
    "States": {
        "Lambda 1": {
        "Type": "Task",
        "Resource": "arn:aws:states:::lambda:invoke",
        "Output": "{% $states.result.Payload %}",
        "Arguments": {
            "FunctionName": "${lambda1.arn}",
            "Payload": "{% $states.input %}"
        },
        "Retry": [
            {
            "ErrorEquals": [
                "Lambda.ServiceException",
                "Lambda.AWSLambdaException",
                "Lambda.SdkClientException",
                "Lambda.TooManyRequestsException"
            ],
            "IntervalSeconds": 1,
            "MaxAttempts": 3,
            "BackoffRate": 2,
            "JitterStrategy": "FULL"
            }
        ],
        "Next": "Lambda 2",
        "Assign": {
            "config": "{% $states.result.Payload %}"
        }
        },
        "Lambda 2": {
        "Type": "Task",
        "Resource": "arn:aws:states:::lambda:invoke",
        "Output": "{% $states.result.Payload %}",
        "Arguments": {
            "FunctionName": "${lambda2.arn}",
            "Payload": "{% $states.input %}"
        },
        "Retry": [
            {
            "ErrorEquals": [
                "Lambda.ServiceException",
                "Lambda.AWSLambdaException",
                "Lambda.SdkClientException",
                "Lambda.TooManyRequestsException"
            ],
            "IntervalSeconds": 1,
            "MaxAttempts": 3,
            "BackoffRate": 2,
            "JitterStrategy": "FULL"
            }
        ],
        "Next": "Lambda 3"
        },
        "Lambda 3": {
        "Type": "Task",
        "Resource": "arn:aws:states:::lambda:invoke",
        "Output": "{% $states.result.Payload %}",
        "Arguments": {
            "FunctionName": "${lambda3.arn}",
            "Payload": {
                "input": "{% $states.input %}",
                "triggerConfig": "{% $config %}"
            }
        },
        "Retry": [
            {
            "ErrorEquals": [
                "Lambda.ServiceException",
                "Lambda.AWSLambdaException",
                "Lambda.SdkClientException",
                "Lambda.TooManyRequestsException"
            ],
            "IntervalSeconds": 1,
            "MaxAttempts": 3,
            "BackoffRate": 2,
            "JitterStrategy": "FULL"
            }
        ],
        "End": true
        }
    },
    "QueryLanguage": "JSONata"
    }`,
    loggingConfiguration: {
        level: "ALL",
        includeExecutionData: true,
        logDestination: pulumi.interpolate`${stepFunctionLogs.arn}:*`
    },
});

// Update the CloudWatch Event Rule to schedule the Step Function every 1 minute
const stepFunctionScheduleRule = new aws.cloudwatch.EventRule("stepFunctionScheduleRule", {
    scheduleExpression: "rate(1 minute)",
});

new aws.cloudwatch.EventTarget("stepFunctionScheduleTarget", {
    rule: stepFunctionScheduleRule.name,
    arn: stepFunction.arn,
    roleArn: stepFunctionRole.arn
});

new aws.iam.RolePolicy("allowEventBridgeToInvokeStepFunction", {
    role: stepFunctionRole.name,
    policy: pulumi.interpolate`{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "states:StartExecution",
                "Resource": "${stepFunction.arn}",
                "Condition": {
                    "ArnEquals": {
                        "aws:SourceArn": "${stepFunctionScheduleRule.arn}"
                    }
                }
            }
        ]
    }`,
});





