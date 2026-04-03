REM 使用 PowerShell 创建一个简单的 ICO 文件
powershell -Command "& {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    
    $bitmap = New-Object System.Drawing.Bitmap(64, 64)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    
    # Clear background
    $graphics.Clear([System.Drawing.Color]::Transparent)
    
    # Draw cat head (green circle)
    $brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 76, 175, 80))
    $graphics.FillEllipse($brush, 10, 10, 44, 44)
    
    # Draw ears (triangles)
    $points1 = @(15, 20), (25, 5), (30, 15)
    $graphics.FillPolygon($brush, $points1)
    
    $points2 = @(45, 20), (35, 5), (30, 15)
    $graphics.FillPolygon($brush, $points2)
    
    # Draw eyes (white with black pupils)
    $whiteBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $blackBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::Black)
    
    $graphics.FillEllipse($whiteBrush, 20, 25, 12, 12)
    $graphics.FillEllipse($whiteBrush, 32, 25, 12, 12)
    
    $graphics.FillEllipse($blackBrush, 22, 27, 6, 6)
    $graphics.FillEllipse($blackBrush, 34, 27, 6, 6)
    
    # Draw nose
    $graphics.FillEllipse($blackBrush, 28, 35, 8, 6)
    
    # Save as PNG first
    $bitmap.Save('logo.png', [System.Drawing.Imaging.ImageFormat]::Png)
    
    # Create icon
    $icon = [System.Drawing.Icon]::ExtractAssociatedIcon([System.Windows.Forms.Application]::ExecutablePath)
    $icon.ExtractAssociatedIcon([System.Windows.Forms.Application]::ExecutablePath).Save('logo.ico')
    
    $graphics.Dispose()
    $bitmap.Dispose()
    $brush.Dispose()
    $whiteBrush.Dispose()
    $blackBrush.Dispose()
}"

echo Logo created: logo.png and logo.ico
