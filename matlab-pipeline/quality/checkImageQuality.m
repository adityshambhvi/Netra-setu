function [result, enhancedImage] = checkImageQuality(inputImage, params)
% CHECKIMAGEQUALITY Stage A: Image Quality Gate for RetinaSense
%
% Syntax:
%   [result, enhancedImage] = checkImageQuality(inputImage)
%   [result, enhancedImage] = checkImageQuality(inputImage, params)
%
% Inputs:
%   inputImage - Either a file path string or an HxWx3 uint8 RGB matrix.
%   params     - (Optional) Struct with tuning thresholds:
%                  .blur_threshold        (default: 35.0)
%                  .min_fov_ratio         (default: 0.20)
%                  .max_fov_ratio         (default: 0.98)
%                  .min_mean_luminance    (default: 30.0)
%                  .max_underexposure_pct (default: 35.0)
%                  .max_overexposure_pct  (default: 12.0)
%
% Outputs:
%   result - Struct with fields:
%              .passed                 - true/false
%              .reason                 - Diagnostic description
%              .recapture_instructions - Actionable instructions for frontline worker
%              .metrics                - Numerical measurements:
%                                          .blur_score
%                                          .tenengrad_score
%                                          .mean_luminance
%                                          .underexposure_pct
%                                          .overexposure_pct
%                                          .fov_ratio
%   enhancedImage - uint8 RGB image after CLAHE and illumination normalization.

    if nargin < 2 || isempty(params)
        params = struct();
    end

    % Set default empirical thresholds
    if ~isfield(params, 'blur_threshold'),        params.blur_threshold = 6.0; end
    if ~isfield(params, 'tenengrad_threshold'),   params.tenengrad_threshold = 60.0; end
    if ~isfield(params, 'min_fov_ratio'),         params.min_fov_ratio = 0.20; end
    if ~isfield(params, 'max_fov_ratio'),         params.max_fov_ratio = 0.98; end
    if ~isfield(params, 'min_mean_luminance'),    params.min_mean_luminance = 30.0; end
    if ~isfield(params, 'max_underexposure_pct'), params.max_underexposure_pct = 35.0; end
    if ~isfield(params, 'max_overexposure_pct'),  params.max_overexposure_pct = 12.0; end

    % Load image if a file path is provided
    if ischar(inputImage) || isstring(inputImage)
        if ~isfile(inputImage)
            error('checkImageQuality:FileNotFound', 'Image file does not exist: %s', inputImage);
        end
        rgbImage = imread(char(inputImage));
    else
        rgbImage = inputImage;
    end

    if size(rgbImage, 3) == 1
        rgbImage = cat(3, rgbImage, rgbImage, rgbImage);
    end

    [H, W, ~] = size(rgbImage);
    totalPixels = H * W;

    redChan   = double(rgbImage(:, :, 1));
    greenChan = double(rgbImage(:, :, 2));
    blueChan  = double(rgbImage(:, :, 3));

    % 1. Retinal Field-of-View (FOV) Segmentation
    % The retina is typically brighter than the surrounding black camera bezel.
    initialMask = (greenChan > 12) | (redChan > 20);
    initialMask = imfill(initialMask, 'holes');
    
    % Retain largest connected component (the retinal fundus circle)
    cc = bwconncomp(initialMask);
    if cc.NumObjects > 0
        numPixels = cellfun(@numel, cc.PixelIdxList);
        [~, maxIdx] = max(numPixels);
        retinalMask = false(size(initialMask));
        retinalMask(cc.PixelIdxList{maxIdx}) = true;
    else
        retinalMask = initialMask;
    end

    % Smooth mask boundaries
    se = strel('disk', round(min(H, W) * 0.01) + 1);
    retinalMask = imclose(retinalMask, se);

    retinalPixelsCount = sum(retinalMask(:));
    fovRatio = retinalPixelsCount / totalPixels;

    % 2. Blur / Sharpness Metric (Laplacian variance on Green channel)
    laplacianKernel = [0,  1, 0;
                       1, -4, 1;
                       0,  1, 0];
    filteredGreen = imfilter(greenChan, laplacianKernel, 'replicate');
    
    if retinalPixelsCount > 100
        laplacianInMask = filteredGreen(retinalMask);
        blurScore = var(laplacianInMask);

        % Secondary sharpness: Tenengrad gradient energy
        [gx, gy] = imgradientxy(greenChan);
        gradEnergy = gx.^2 + gy.^2;
        tenengradScore = mean(gradEnergy(retinalMask));
    else
        blurScore = 0;
        tenengradScore = 0;
    end

    % 3. Exposure & Illumination (Evaluated strictly inside retinal mask)
    if retinalPixelsCount > 100
        maskIntensities = greenChan(retinalMask);
        meanLuminance = mean(maskIntensities);
        underexposedCount = sum(maskIntensities < 25);
        overexposedCount  = sum(maskIntensities > 235);
        
        underexposurePct = (underexposedCount / retinalPixelsCount) * 100.0;
        overexposurePct  = (overexposedCount  / retinalPixelsCount) * 100.0;
    else
        meanLuminance = 0;
        underexposurePct = 100.0;
        overexposurePct = 0.0;
    end

    % 4. Decision Rule Engine & Frontline Recapture Diagnostics
    passed = true;
    reasons = {};
    recaptureInstructions = {};

    % FOV check
    if fovRatio < params.min_fov_ratio
        passed = false;
        reasons{end+1} = sprintf('Field of view too small (%.1f%% of frame, minimum is %.1f%%)', fovRatio * 100, params.min_fov_ratio * 100);
        recaptureInstructions{end+1} = 'Camera alignment issue: Center the camera lens directly over the patient pupil and bring it closer to capture the full retina.';
    elseif fovRatio > params.max_fov_ratio && meanLuminance < 15
        passed = false;
        reasons{end+1} = 'Blank or occluded capture detected.';
        recaptureInstructions{end+1} = 'Check lens cap or sensor occlusion, ensure camera illumination light is active, and recapture.';
    end

    % Blur check
    if blurScore < params.blur_threshold || tenengradScore < params.tenengrad_threshold
        passed = false;
        reasons{end+1} = sprintf('Severe blur detected (sharpness: blur=%.1f < %.1f, tenengrad=%.1f < %.1f)', ...
            blurScore, params.blur_threshold, tenengradScore, params.tenengrad_threshold);
        recaptureInstructions{end+1} = 'Motion or defocus blur: Stabilize the camera, ask the patient to hold gaze at the fixation target, and turn the focus ring until retinal vessels are crisp.';
    end

    % Exposure checks
    if meanLuminance < params.min_mean_luminance || underexposurePct > params.max_underexposure_pct
        passed = false;
        reasons{end+1} = sprintf('Underexposed / insufficient light (mean luminance %.1f, %.1f%% underexposed pixels)', meanLuminance, underexposurePct);
        recaptureInstructions{end+1} = 'Underexposure: Increase fundus camera LED brightness or allow patient eye 60 seconds to dilate in a dimmer room.';
    end

    if overexposurePct > params.max_overexposure_pct
        passed = false;
        reasons{end+1} = sprintf('Specular glare / overexposure detected (%.1f%% saturated pixels)', overexposurePct);
        recaptureInstructions{end+1} = 'Corneal glare / flash reflection: Slightly adjust camera angle relative to the eye to eliminate white glare spots.';
    end

    % 5. Image Enhancement Branch (CLAHE + Illumination Normalization)
    % Convert to Lab color space so chromaticity is preserved while boosting vessel/lesion contrast
    try
        labImage = rgb2lab(rgbImage);
        L = labImage(:, :, 1) / 100.0; % Normalize L to [0, 1]
        
        % CLAHE on Luminance
        L_enhanced = adapthisteq(L, 'ClipLimit', 0.015, 'Distribution', 'uniform', 'NumTiles', [8, 8]);
        labImage(:, :, 1) = L_enhanced * 100.0;
        enhancedRgb = lab2rgb(labImage);
        
        % Denoising filter
        enhancedRgb = imgaussfilt(enhancedRgb, 0.5);
        enhancedImage = uint8(min(max(enhancedRgb * 255.0, 0), 255));
    catch
        % Fallback green-channel CLAHE if colorspace conversion fails
        G_eq = adapthisteq(uint8(greenChan), 'ClipLimit', 0.015);
        enhancedImage = rgbImage;
        enhancedImage(:, :, 2) = G_eq;
    end

    % Pack result struct
    result = struct();
    result.passed = passed;
    if passed
        result.reason = 'Pass: Image quality satisfies diagnostic resolution and illumination criteria.';
        result.recapture_instructions = 'N/A (Ready for DR screening)';
    else
        result.reason = strjoin(reasons, ' | ');
        result.recapture_instructions = strjoin(recaptureInstructions, ' ');
    end

    result.metrics = struct(...
        'blur_score', blurScore, ...
        'tenengrad_score', tenengradScore, ...
        'mean_luminance', meanLuminance, ...
        'underexposure_pct', underexposurePct, ...
        'overexposure_pct', overexposurePct, ...
        'fov_ratio', fovRatio ...
    );
end
