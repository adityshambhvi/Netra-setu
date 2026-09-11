function result = runScreening(image_path)
% RUNSCREENING Master pipeline orchestrator for RetinaSense / Netra-setu.
%
% Syntax:
%   result = runScreening(image_path)
%
% Input:
%   image_path - Path to retinal fundus image file.
%
% Output:
%   result - Consolidated struct with fields:
%              .pass               - Boolean (true if passed quality gate)
%              .reason             - Overall status description
%              .grade              - Integer predicted ICDR grade (0..4)
%              .grade_label        - Descriptive string for DR grade
%              .referral           - Boolean referral decision
%              .why_refer          - Plain-language explanation for frontline worker
%              .evidence_list      - Cell array of evidence findings
%              .confidence         - Float percentage (0..100)
%              .overlay_image_path - Path to saved evidence overlay image
%              .quality_status     - Struct from checkImageQuality

    % Ensure matlab-pipeline folders are on MATLAB path
    currentDir = fileparts(mfilename('fullpath'));
    addpath(currentDir);
    addpath(fullfile(currentDir, 'quality'));

    % Persistent network cache to load ONNX models only once
    persistent cachedModels;
    if isempty(cachedModels) || ~isfield(cachedModels, 'loaded') || ~cachedModels.loaded
        fprintf('[MATLAB Pipeline] Initializing ONNX models at startup...\n');
        cachedModels = loadModels();
    end

    if ~isfile(image_path)
        error('runScreening:FileNotFound', 'Input image file does not exist: %s', image_path);
    end

    % 1. Stage A: Image Quality Gate
    fprintf('[MATLAB Pipeline] Running Stage A: Image Quality Gate on %s...\n', image_path);
    [quality_status, enhanced_image] = checkImageQuality(image_path);

    % Prepare output directory for overlay images
    backendDir = fullfile(currentDir, '..', 'backend');
    overlayDir = fullfile(backendDir, 'static', 'overlays');
    if ~exist(overlayDir, 'dir')
        mkdir(overlayDir);
    end

    if ~quality_status.passed
        fprintf('[MATLAB Pipeline] Stage A Quality Gate FAILED: %s\n', quality_status.reason);
        result = struct();
        result.pass               = false;
        result.reason             = sprintf('Quality Gate Failed: %s', quality_status.reason);
        result.grade              = int32(0);
        result.grade_label        = 'Unscreenable (Quality Gate Failed)';
        result.referral           = false;
        result.why_refer          = sprintf('Quality Gate Rejected: %s. Frontline Action: %s', quality_status.reason, quality_status.recapture_instructions);
        result.evidence_list      = {{sprintf('Quality Gate Failure: %s', quality_status.reason)}};
        result.confidence         = 0.0;
        result.overlay_image_path = '';
        result.quality_status     = quality_status;
        return;
    end

    % 2. Stage B Track 1: Lesion Detection
    fprintf('[MATLAB Pipeline] Running Stage B Track 1: Lesion Detection...\n');
    lesion_res = detectLesions(cachedModels.seg_net, enhanced_image);

    % 3. Stage B Track 2: DR Grading CNN & Grad-CAM
    fprintf('[MATLAB Pipeline] Running Stage B Track 2: ResNet-18 DR Grading & Grad-CAM...\n');
    grade_res = gradeDR(cachedModels.grading_net, enhanced_image);

    % 4. Stage C: Evidence Combiner
    fprintf('[MATLAB Pipeline] Running Stage C: Evidence Combiner...\n');
    evidence_res = combineEvidence(lesion_res, grade_res, enhanced_image);

    % 5. Save Overlay Image to Disk
    [~, baseName, ~] = fileparts(image_path);
    timestampStr = datestr(now, 'yyyymmdd_HHMMSS');
    overlayFileName = sprintf('overlay_%s_%s.jpg', baseName, timestampStr);
    overlayFullPath = fullfile(overlayDir, overlayFileName);
    imwrite(evidence_res.overlay_image, overlayFullPath, 'jpg', 'Quality', 92);

    % Relative web path for Flask server
    overlayWebPath = sprintf('/overlays/%s', overlayFileName);

    gradeLabels = {
        'Grade 0: No Diabetic Retinopathy', ...
        'Grade 1: Mild Non-Proliferative DR', ...
        'Grade 2: Moderate Non-Proliferative DR', ...
        'Grade 3: Severe Non-Proliferative DR', ...
        'Grade 4: Proliferative DR'
    };
    gradeIdx = min(max(grade_res.grade + 1, 1), 5);
    gradeLabel = gradeLabels{gradeIdx};

    % Pack consolidated return struct
    result = struct();
    result.pass               = true;
    result.reason             = 'Screening completed successfully.';
    result.grade              = int32(grade_res.grade);
    result.grade_label        = gradeLabel;
    result.referral           = evidence_res.referral;
    result.why_refer          = evidence_res.why_refer;
    result.evidence_list      = evidence_res.evidence_list;
    result.confidence         = double(max(grade_res.probabilities) * 100.0);
    result.overlay_image_path = overlayWebPath;
    result.quality_status     = quality_status;
end
