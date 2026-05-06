import Foundation

public struct RuntimeAuthority {
    public static let shared = RuntimeAuthority()
    
    public var workingDirectory: String {
        return FileManager.default.currentDirectoryPath
    }
    
    public func shutdown(exitCode: Int32) {
        exit(exitCode)
    }
}
