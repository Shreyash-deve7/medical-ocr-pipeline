<#
.SYNOPSIS
    Finds available (free) TCP ports on the local machine.
.DESCRIPTION
    Scans a range of TCP ports to see which ones are not currently being used by any listening services or active connections.
.PARAMETER MinPort
    The lower bound of the port range to check. Default is 3000.
.PARAMETER MaxPort
    The upper bound of the port range to check. Default is 9000.
.PARAMETER Count
    The maximum number of free ports to return. Default is 30.
.EXAMPLE
    .\find_free_ports.ps1 -MinPort 8000 -MaxPort 9000 -Count 10
#>
param(
    [int]$MinPort = 3000,
    [int]$IdUpperLimit = 65535, # Max possible port number
    [int]$MaxPort = 9000,
    [int]$Count = 30
)

# Validate input ranges
if ($MinPort -lt 1 -or $MinPort -gt 65535) {
    Write-Error "MinPort must be between 1 and 65535."
    return
}
if ($MaxPort -lt $MinPort -or $MaxPort -gt 65535) {
    Write-Error "MaxPort must be between MinPort ($MinPort) and 65535."
    return
}
if ($Count -le 0) {
    Write-Error "Count must be greater than 0."
    return
}

Write-Host "Scanning for available TCP ports in range [$MinPort - $MaxPort]..." -ForegroundColor Cyan

try {
    # Get active TCP listeners and active connections
    $properties = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties()
    
    # Get ports that are actively listening
    $listeners = $properties.GetActiveTcpListeners()
    $listenerPorts = $listeners.Port
    
    # Get ports that are active connections (both local and remote, but we care about local endpoint)
    $connections = $properties.GetActiveTcpConnections()
    $connectionPorts = $connections.LocalEndPoint.Port

    # Combine all active ports into a hash set for O(1) lookups
    $usedPorts = [System.Collections.Generic.HashSet[int]]::new()
    foreach ($port in $listenerPorts) {
        [void]$usedPorts.Add($port)
    }
    foreach ($port in $connectionPorts) {
        [void]$usedPorts.Add($port)
    }

    # Find free ports
    $freePorts = [System.Collections.Generic.List[int]]::new()
    for ($port = $MinPort; $port -le $MaxPort; $port++) {
        if (-not $usedPorts.Contains($port)) {
            $freePorts.Add($port)
            if ($freePorts.Count -ge $Count) {
                break
            }
        }
    }

    if ($freePorts.Count -eq 0) {
        Write-Host "No free ports found in the range $MinPort - $MaxPort." -ForegroundColor Yellow
    } else {
        Write-Host "Found $($freePorts.Count) available ports:" -ForegroundColor Green
        $freePorts | ForEach-Object {
            Write-Host "  - $_" -ForegroundColor White
        }
        # Output the list to pipeline
        return $freePorts
    }
}
catch {
    Write-Error "An error occurred while scanning ports: $_"
}
