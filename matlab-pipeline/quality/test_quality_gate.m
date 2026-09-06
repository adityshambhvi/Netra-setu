% TEST_QUALITY_GATE Unit and stress tests for checkImageQuality.m
% Run this script in MATLAB to validate the Quality Gate logic.

fprintf('=== Running RetinaSense Quality Gate Tests ===\n');

% Add quality directory to path
scriptDir = fileparts(mfilename('fullpath'));
addpath(scriptDir);

% Find sample test image in Dataset
datasetBase = fullfile(scriptDir, '..', '..', 'Dataset', 'IEEE diabetic retinopathy', ...
    'A. Segmentation', 'A. Segmentation', '1. Original Images', 'a. Training Set');

sampleFile = fullfile(datasetBase, 'IDRiD_01.jpg');
if ~isfile(sampleFile)
    error('Could not find sample image: %s', sampleFile);
end

fprintf('Loading sample benchmark image: %s\n', sampleFile);
sampleImg = imread(sampleFile);

% Test 1: Clean baseline image should PASS
fprintf('\n[Test 1] Testing clean baseline IDRiD image...\n');
[resClean, enhClean] = checkImageQuality(sampleImg);
fprintf('Result: Passed=%d, BlurScore=%.2f, MeanLum=%.2f, FOVRatio=%.2f\n', ...
    resClean.passed, resClean.metrics.blur_score, resClean.metrics.mean_luminance, resClean.metrics.fov_ratio);
assert(resClean.passed == true, 'Test 1 Failed: Clean image must pass quality gate!');
assert(isequal(size(enhClean), size(sampleImg)), 'Test 1 Failed: Enhanced image size mismatch');
fprintf('✓ Test 1 Passed!\n');

% Test 2: Severe Defocus Blur should FAIL
fprintf('\n[Test 2] Testing synthetic severe blur...\n');
hBlur = fspecial('gaussian', [25 25], 8.0);
blurredImg = imfilter(sampleImg, hBlur, 'replicate');
[resBlur, ~] = checkImageQuality(blurredImg);
fprintf('Result: Passed=%d, Reason="%s"\n', resBlur.passed, resBlur.reason);
assert(resBlur.passed == false, 'Test 2 Failed: Blurred image must be rejected');
assert(contains(resBlur.reason, 'Severe blur'), 'Test 2 Failed: Did not detect blur reason');
fprintf('✓ Test 2 Passed!\n');

% Test 3: Severe Underexposure should FAIL
fprintf('\n[Test 3] Testing synthetic underexposure...\n');
darkImg = uint8(double(sampleImg) * 0.15);
[resDark, ~] = checkImageQuality(darkImg);
fprintf('Result: Passed=%d, Reason="%s"\n', resDark.passed, resDark.reason);
assert(resDark.passed == false, 'Test 3 Failed: Dark image must be rejected');
assert(contains(resDark.reason, 'Underexposed'), 'Test 3 Failed: Did not detect underexposure reason');
fprintf('✓ Test 3 Passed!\n');

% Test 4: Specular Glare / Flash Overexposure should FAIL
fprintf('\n[Test 4] Testing synthetic corneal glare...\n');
glareImg = sampleImg;
[H, W, ~] = size(glareImg);
[X, Y] = meshgrid(1:W, 1:H);
cx = round(W / 2); cy = round(H / 2);
glareMask = ((X - cx).^2 + (Y - cy).^2) < (min(H, W) * 0.20)^2;
glareImg(cat(3, glareMask, glareMask, glareMask)) = 255;
[resGlare, ~] = checkImageQuality(glareImg);
fprintf('Result: Passed=%d, Reason="%s"\n', resGlare.passed, resGlare.reason);
assert(resGlare.passed == false, 'Test 4 Failed: Glare image must be rejected');
assert(contains(resGlare.reason, 'overexposure') || contains(resGlare.reason, 'glare'), 'Test 4 Failed: Did not detect glare');
fprintf('✓ Test 4 Passed!\n');

% Test 5: Off-center / Tiny FOV should FAIL
fprintf('\n[Test 5] Testing tiny field-of-view / sensor occlusion...\n');
occludedImg = zeros(size(sampleImg), 'uint8');
occludedImg(1:round(H*0.2), 1:round(W*0.2), :) = sampleImg(1:round(H*0.2), 1:round(W*0.2), :);
[resFOV, ~] = checkImageQuality(occludedImg);
fprintf('Result: Passed=%d, Reason="%s"\n', resFOV.passed, resFOV.reason);
assert(resFOV.passed == false, 'Test 5 Failed: Occluded image must be rejected');
fprintf('✓ Test 5 Passed!\n');

fprintf('\n=======================================================\n');
fprintf('ALL 5 QUALITY GATE UNIT TESTS PASSED SUCCESSFULLY!\n');
fprintf('=======================================================\n');
