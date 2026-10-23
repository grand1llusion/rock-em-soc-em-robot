# Deploy (AWS Console, us-east-1)

1. **DynamoDB** > Create table: name `rock-em-cases`, partition key `alert_id` (String), on-demand capacity.
2. **IAM** role `rock-em-soc-em-robot-role` (Lambda trust) with `AWSLambdaBasicExecutionRole`,
   Bedrock access and DynamoDB access. For anything beyond a demo, scope Bedrock to `bedrock:InvokeModel`
   on the chosen model/inference profile and DynamoDB to `PutItem` on the one table.
3. **Lambda** > Create function `rock-em-soc-em-robot`: Python 3.12 or newer, use the existing role above.
   - Upload `dist/rock-em-soc-em-robot.zip` (Code > Upload from > .zip file).
   - Configuration > General: memory 256 MB, timeout 60 s.
   - Configuration > Environment variables: `MODEL_ID` = your Nova inference profile ID
     (default `us.amazon.nova-lite-v1:0`). Optional: `ACCESS_CODE` to require a passcode.
   - Configuration > Function URL > Create: auth type `NONE`, save. (Open the URL to use the app.)
   - Optional cost guard: Configuration > Concurrency > reserve 2.
4. **Amazon Location Service** (the `locate_place` tool): no resource to create. Add an inline policy to
   the role from `docs/iam-location-policy.json`: it allows only `geo-places:Geocode` in us-east-1.
   Without it the robot still works, but places outside its built-in city table come back
   "lookup failed (AccessDeniedException)".
5. **AWS Budgets**: zero-spend or small monthly budget with an email alert.
